#pragma once
#include <nlohmann/json.hpp>
#include <cstdint>
#include <deque>
#include <optional>
#include <string>
#include <vector>

namespace lab {
using Json = nlohmann::json;
struct Rejection : std::runtime_error {
  std::string code;
  Rejection(std::string c, std::string message)
      : std::runtime_error(std::move(message)), code(std::move(c)) {}
};
struct Step { double setpoint; int ticks; };
struct Recipe {
  int rate;
  std::uint32_t seed;
  std::vector<Step> steps;
  int total_ticks;
  static Recipe parse(const Json& value);
};
class Noise {
  std::uint32_t state_;
 public:
  explicit Noise(std::uint32_t seed) : state_(seed ? seed : 1) {}
  double next();
};
class Engine {
  std::optional<Recipe> recipe_;
  Noise response_noise_{1}, reference_noise_{2};
  int segment_ = 0, segment_tick_ = 0;
  double response_ = 0;
 public:
  std::string state = "IDLE", run_id, reason;
  int final_seq = -1;
  double output = 0;
  void start(const std::string& run, const Json& recipe, bool telemetry_ready);
  void stop(const std::string& run);
  void fault(const std::string& why);
  void reset();
  std::optional<Json> tick();
  int rate() const { return recipe_ ? recipe_->rate : 50; }
  Json status() const;
};
struct CommandRecord { std::string id, payload, run; Json response; double at; };
class CommandCache {
  std::deque<CommandRecord> entries_;
 public:
  static constexpr std::size_t capacity = 256;
  static constexpr double retention_seconds = 120;
  std::optional<Json> lookup(const std::string& id, const Json& payload,
                             double now, const std::string& active_run);
  void remember(const std::string& id, const Json& payload, const Json& response,
                double now);
};
} // namespace lab
