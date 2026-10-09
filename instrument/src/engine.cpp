#include "engine.hpp"
#include <algorithm>
#include <cmath>

namespace lab {
namespace {
int integer(const Json& object, const char* key, int lo, int hi) {
  if (!object.contains(key) || !object.at(key).is_number_integer())
    throw Rejection("INVALID_RECIPE", std::string(key) + " must be an integer");
  const auto number = object.at(key).get<std::int64_t>();
  if (number < lo || number > hi)
    throw Rejection("INVALID_RECIPE", std::string(key) + " outside allowed bounds");
  return static_cast<int>(number);
}
}
Recipe Recipe::parse(const Json& value) {
  if (!value.is_object() || value.size() != 3)
    throw Rejection("INVALID_RECIPE", "Recipe requires sample_rate_hz, seed and steps");
  Recipe result{integer(value, "sample_rate_hz", 10, 100), 1, {}, 0};
  if (result.rate != 10 && result.rate != 20 && result.rate != 25 &&
      result.rate != 50 && result.rate != 100)
    throw Rejection("INVALID_RECIPE", "Unsupported sample rate");
  result.seed = static_cast<std::uint32_t>(integer(value, "seed", 1, 2147483647));
  if (!value.contains("steps") || !value["steps"].is_array() ||
      value["steps"].empty() || value["steps"].size() > 8)
    throw Rejection("INVALID_RECIPE", "Expected one to eight steps");
  for (const auto& item : value["steps"]) {
    if (!item.is_object() || item.size() != 2 || !item.contains("setpoint") ||
        !item["setpoint"].is_number())
      throw Rejection("INVALID_RECIPE", "Step requires setpoint and duration_ms");
    const auto u = item["setpoint"].get<double>();
    if (!std::isfinite(u) || u < 0 || u > 1)
      throw Rejection("INVALID_RECIPE", "Setpoint must be between zero and one");
    const int duration = integer(item, "duration_ms", 10, 60000);
    const int period = 1000 / result.rate;
    if (duration % period != 0)
      throw Rejection("INVALID_RECIPE", "Duration must contain whole sample periods");
    const int ticks = duration / period;
    result.total_ticks += ticks;
    result.steps.push_back({u, ticks});
  }
  if (result.total_ticks > result.rate * 60)
    throw Rejection("INVALID_RECIPE", "Run duration exceeds sixty seconds");
  return result;
}

double Noise::next() {
  // xorshift32, followed by a uniform mapping to [-0.02, 0.02).
  // Two independent streams; fault injection will not consume either stream.
  state_ ^= state_ << 13;
  state_ ^= state_ >> 17;
  state_ ^= state_ << 5;
  return (static_cast<double>(state_) / 4294967296.0 - 0.5) * 0.04;
}
void Engine::start(const std::string& run, const Json& recipe, bool ready) {
  if (state == "RUNNING") throw Rejection("BUSY", "An experiment is already running");
  if (state == "FAULTED") throw Rejection("NEEDS_RESET", "Acknowledge the fault first");
  if (!ready) throw Rejection("TELEMETRY_UNAVAILABLE", "Telemetry subscriber required");
  if (run.empty() || run.size() > 64 || run == run_id)
    throw Rejection("INVALID_RUN", "A new bounded run ID is required");
  auto validated = Recipe::parse(recipe);
  recipe_ = std::move(validated);
  response_noise_ = Noise(recipe_->seed);
  reference_noise_ = Noise(recipe_->seed ^ 0x9e3779b9U);
  run_id = run;
  state = "RUNNING";
  reason.clear();
  segment_ = segment_tick_ = 0;
  final_seq = -1;
  response_ = 0;
  output = recipe_->steps.front().setpoint;
}
void Engine::stop(const std::string& run) {
  if (run_id.empty() || run != run_id)
    throw Rejection("STALE_RUN", "Stop does not target the current run");
  if (state == "RUNNING") {
    output = 0;
    state = "STOPPED";
    reason = "operator_stop";
  }
}
void Engine::fault(const std::string& why) {
  if (state == "RUNNING") {
    output = 0;
    state = "FAULTED";
    reason = why;
  }
}
void Engine::reset() {
  if (state != "FAULTED") throw Rejection("INVALID_STATE", "Only a fault needs reset");
  state = "IDLE";
  reason.clear();
  // Retain last run/final sequence for reconciliation until a new start.
}
std::optional<Json> Engine::tick() {
  if (state != "RUNNING") return std::nullopt;
  const auto& step = recipe_->steps.at(segment_);
  output = step.setpoint;
  const double dt = 1.0 / recipe_->rate;
  response_ = output + (response_ - output) * std::exp(-dt / 0.5);
  ++final_seq;
  Json sample{{"seq", final_seq}, {"logical_s", (final_seq + 1) * dt},
              {"setpoint", output}, {"response", response_ + response_noise_.next()},
              {"reference", 0.8 * response_ + reference_noise_.next()}};
  if (++segment_tick_ == step.ticks) {
    ++segment_;
    segment_tick_ = 0;
  }
  if (final_seq + 1 == recipe_->total_ticks) {
    output = 0;
    state = "COMPLETED";
    reason = "recipe_complete";
  }
  return sample;
}
Json Engine::status() const {
  return {{"state", state}, {"run_id", run_id}, {"final_seq", final_seq},
          {"output", output}, {"reason", reason}};
}
std::optional<Json> CommandCache::lookup(const std::string& id, const Json& payload,
                                         double now, const std::string& active) {
  std::erase_if(entries_, [&](const auto& entry) {
    return now - entry.at > retention_seconds && (active.empty() || entry.run != active);
  });
  for (const auto& entry : entries_) {
    if (entry.id != id) continue;
    if (entry.payload != payload.dump())
      throw Rejection("COMMAND_CONFLICT", "Command ID was used with different content");
    return entry.response;
  }
  if (entries_.size() >= capacity)
    throw Rejection("COMMAND_CAPACITY", "Retry record capacity reached");
  return std::nullopt;
}
void CommandCache::remember(const std::string& id, const Json& payload,
                            const Json& response, double now) {
  entries_.push_back({id, payload.dump(), payload.value("run_id", ""), response, now});
}
} // namespace lab
