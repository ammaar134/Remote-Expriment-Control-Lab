#include "engine.hpp"
#include <asio.hpp>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <ctime>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <random>
#include <sstream>

using asio::ip::tcp;
using Clock = std::chrono::steady_clock;
using lab::Json;
constexpr std::size_t max_frame = 65536;
constexpr std::size_t max_queue = 128;
constexpr std::size_t retained_limit = 512;

std::string utc_now() {
  const auto now = std::chrono::system_clock::now();
  const auto seconds = std::chrono::system_clock::to_time_t(now);
  const auto micros = std::chrono::duration_cast<std::chrono::microseconds>(
    now.time_since_epoch()).count() % 1000000;
  std::tm time{};
  gmtime_r(&seconds, &time);
  std::ostringstream result;
  result << std::put_time(&time, "%Y-%m-%dT%H:%M:%S") << '.'
         << std::setw(6) << std::setfill('0') << micros << 'Z';
  return result.str();
}
std::string boot_identifier() {
  std::random_device random;
  std::ostringstream value;
  for (int i=0; i<4; ++i) value << std::hex << std::setw(8) << std::setfill('0') << random();
  return value.str();
}
std::string identifier(const Json& value, const char* key) {
  if (!value.contains(key) || !value[key].is_string())
    throw lab::Rejection("INVALID_MESSAGE", std::string(key) + " must be a string");
  auto id = value[key].get<std::string>();
  if (id.empty() || id.size() > 64)
    throw lab::Rejection("INVALID_MESSAGE", std::string(key) + " length outside bounds");
  return id;
}
class Channel : public std::enable_shared_from_this<Channel> {
  tcp::socket socket_;
  std::string input_;
  std::deque<std::shared_ptr<std::string>> outgoing_;
  bool closed_ = false;
 public:
  bool ready = false;
  std::function<void(Channel&, const Json&)> message;
  std::function<void(Channel&)> disconnected;
  std::function<void()> writable;
  explicit Channel(tcp::socket socket) : socket_(std::move(socket)) {}
  void close() {
    if (closed_) return;
    closed_ = true;
    asio::error_code ignored;
    socket_.shutdown(tcp::socket::shutdown_both, ignored);
    socket_.close(ignored);
    if (disconnected) disconnected(*this);
  }
  bool send(const Json& payload) {
    if (closed_ || outgoing_.size() >= max_queue) { close(); return false; }
    auto frame = std::make_shared<std::string>(payload.dump() + "\n");
    if (frame->size() > max_frame) { close(); return false; }
    outgoing_.push_back(frame);
    if (outgoing_.size() == 1) write();
    return true;
  }
  std::size_t queued() const { return outgoing_.size(); }
  void read() {
    auto self = shared_from_this();
    asio::async_read_until(socket_, asio::dynamic_buffer(input_, max_frame), '\n',
      [self](const asio::error_code& error, std::size_t count) {
        if (error || count > max_frame) { self->close(); return; }
        auto frame = self->input_.substr(0, count);
        self->input_.erase(0, count);
        const auto parsed = Json::parse(frame, nullptr, false);
        if (parsed.is_discarded() || !parsed.is_object()) { self->close(); return; }
        self->message(*self, parsed);
        if (!self->closed_) self->read();
      });
  }
 private:
  void write() {
    auto self = shared_from_this();
    auto frame = outgoing_.front(); // Keep the bytes alive until completion.
    asio::async_write(socket_, asio::buffer(*frame),
      [self, frame](const asio::error_code& error, std::size_t) {
        if (error) { self->close(); return; }
        self->outgoing_.pop_front();
        if (!self->closed_ && !self->outgoing_.empty()) self->write();
        if (!self->closed_ && self->writable) self->writable();
      });
  }
};
class Server {
  asio::io_context& io_;
  tcp::acceptor control_listener_, telemetry_listener_;
  asio::steady_timer tick_timer_, lease_timer_;
  std::shared_ptr<Channel> control_, telemetry_;
  lab::Engine engine_;
  lab::CommandCache cache_;
  std::deque<Json> retained_;
  int acknowledged_ = -1, sent_ = -1;
  const bool faults_enabled_ = std::getenv("LAB_ENABLE_FAULTS") &&
    std::string(std::getenv("LAB_ENABLE_FAULTS")) == "1";
  std::string instrument_, boot_ = boot_identifier();
  Clock::time_point boot_time_ = Clock::now(), run_start_, last_control_ = Clock::now();
  double elapsed() const {
    return std::chrono::duration<double>(Clock::now() - boot_time_).count();
  }
  Json envelope(const std::string& type) const {
    return {{"v", 1}, {"type", type}, {"instrument_id", instrument_}, {"boot_id", boot_}};
  }
  Json observed() const {
    auto value = engine_.status();
    value["telemetry_ready"] = telemetry_ && telemetry_->ready;
    value["queued_frames"] = telemetry_ ? telemetry_->queued() : 0;
    value["retained_samples"] = retained_.size();
    value["retention_capacity"] = retained_limit;
    value["acknowledged_seq"] = acknowledged_;
    return value;
  }
  void acknowledge(const Json& request) {
    if (identifier(request, "run_id") != engine_.run_id)
      throw lab::Rejection("STALE_RUN", "Acknowledgement targets another run");
    if (!request.contains("persisted_seq") || !request["persisted_seq"].is_number_integer())
      throw lab::Rejection("INVALID_ACK", "Persisted sequence must be an integer");
    const auto seq = request["persisted_seq"].get<std::int64_t>();
    if (seq < -1 || seq > sent_)
      throw lab::Rejection("INVALID_ACK", "Cannot acknowledge unsent samples");
    if (seq <= acknowledged_) return;
    acknowledged_ = static_cast<int>(seq);
    while (!retained_.empty() && retained_.front()["seq"].get<int>() <= acknowledged_)
      retained_.pop_front();
  }
  void pump() {
    if (!telemetry_ || !telemetry_->ready) return;
    // Socket writes are bounded independently from durable retention. A reconnect
    // resets the send cursor; only a committed cumulative ACK releases samples.
    while (telemetry_ && telemetry_->queued() < 8) {
      Json samples = Json::array();
      for (const auto& sample : retained_) {
        if (sample["seq"].get<int>() > sent_) {
          samples.push_back(sample);
          if (samples.size() == 25) break;
        }
      }
      if (samples.empty()) return;
      auto frame = envelope("samples");
      frame["run_id"] = engine_.run_id;
      frame["samples"] = samples;
      sent_ = samples.back()["seq"].get<int>();
      auto connection = telemetry_;
      if (!connection->send(frame)) return;
    }
  }
  void fault(const std::string& why) {
    const bool was_running = engine_.state == "RUNNING";
    engine_.fault(why);
    if (was_running) {
      tick_timer_.cancel();
      std::cout << Json{{"event", "fault"}, {"run_id", engine_.run_id},
                         {"reason", why}}.dump() << std::endl;
    }
  }
  void validate(const Json& request) {
    if (!request.contains("v") || !request["v"].is_number_integer() || request["v"] != 1)
      throw lab::Rejection("VERSION_UNSUPPORTED", "Protocol v1 required");
    if (identifier(request, "instrument_id") != instrument_)
      throw lab::Rejection("WRONG_INSTRUMENT", "Instrument identity mismatch");
  }
  void handle(Channel& channel, const Json& request, bool telemetry) {
    Json response = envelope("response");
    response["request_id"] = request.value("request_id", Json(nullptr));
    try {
      validate(request);
      identifier(request, "request_id");
      const auto type = identifier(request, "type");
      if (!channel.ready) {
        if ((!telemetry && type != "handshake") || (telemetry && type != "subscribe"))
          throw lab::Rejection("HANDSHAKE_REQUIRED", "Connection must first identify itself");
        if (telemetry && request.value("boot_id", "") != boot_)
          throw lab::Rejection("STALE_BOOT", "Boot identity mismatch");
        channel.ready = true;
        if (!telemetry) last_control_ = Clock::now();
        response["ok"] = true;
        response["status"] = observed();
        response["engine_version"] = "0.2.0";
        channel.send(response);
        if (telemetry) { sent_ = acknowledged_; pump(); }
        return;
      }
      if (telemetry) throw lab::Rejection("INVALID_MESSAGE", "Send durability ACKs on control");
      if (request.value("boot_id", "") != boot_)
        throw lab::Rejection("STALE_BOOT", "Boot identity mismatch");
      last_control_ = Clock::now();
      if (type == "ack") {
        acknowledge(request);
        response["ok"] = true;
        response["persisted_seq"] = acknowledged_;
        channel.send(response);
        return;
      }
      if (type == "status" || type == "heartbeat") {
        response["ok"] = true;
        response["status"] = observed();
        channel.send(response);
        return;
      }
      if (type != "start" && type != "stop" && type != "reset")
        throw lab::Rejection("UNKNOWN_COMMAND", "Unsupported control message");
      if (type == "reset" && request.contains("run_id")) identifier(request, "run_id");
      const auto id = identifier(request, "command_id");
      // Correlation IDs are part of an identical retry payload.
      auto cached = cache_.lookup(id, request, elapsed(),
                                  engine_.state == "RUNNING" ? engine_.run_id : "");
      if (cached) { channel.send(*cached); return; }
      try {
        if (type == "start") {
          const auto scenario = request.value("scenario", "normal");
          if (scenario != "normal" && (!faults_enabled_ || scenario != "lost_start_ack"))
            throw lab::Rejection("FAULTS_DISABLED", "Fault scenario not enabled");
          if (!retained_.empty())
            throw lab::Rejection("UNACKNOWLEDGED_DATA", "Previous run has uncommitted samples");
          engine_.start(identifier(request, "run_id"), request.at("recipe"),
                        telemetry_ && telemetry_->ready);
          acknowledged_ = sent_ = -1;
          run_start_ = Clock::now();
          schedule_tick();
        } else if (type == "stop") {
          engine_.stop(identifier(request, "run_id"));
          tick_timer_.cancel();
        } else {
          engine_.reset();
          retained_.clear();
          acknowledged_ = sent_ = -1;
        }
        response["ok"] = true;
        response["applied"] = true;
        response["status"] = observed();
      } catch (const lab::Rejection& error) {
        response["ok"] = false;
        response["error"] = {{"code", error.code}, {"message", error.what()}};
        response["status"] = observed();
      }
      cache_.remember(id, request, response, elapsed());
      // Explicit local/test scenario: lose one application response, not TCP data.
      // The cached reply remains available to an identical command retry.
      if (response.value("ok", false) && type == "start" &&
          request.value("scenario", "normal") == "lost_start_ack") return;
      channel.send(response);
    } catch (const lab::Rejection& error) {
      response["ok"] = false;
      response["error"] = {{"code", error.code}, {"message", error.what()}};
      channel.send(response);
    } catch (const Json::exception&) {
      response["ok"] = false;
      response["error"] = {{"code", "INVALID_MESSAGE"}, {"message", "Missing or invalid fields"}};
      channel.send(response);
    }
  }
  void accept(bool is_telemetry) {
    auto& listener = is_telemetry ? telemetry_listener_ : control_listener_;
    listener.async_accept([this, is_telemetry](const asio::error_code& error, tcp::socket socket) {
      if (!error) {
        auto& slot = is_telemetry ? telemetry_ : control_;
        if (slot) { asio::error_code ignored; socket.close(ignored); }
        else {
          if (is_telemetry) socket.set_option(asio::socket_base::send_buffer_size(8192));
          auto channel = std::make_shared<Channel>(std::move(socket));
          slot = channel;
          if (!is_telemetry) last_control_ = Clock::now();
          channel->message = [this, is_telemetry](Channel& c, const Json& j) {
            handle(c, j, is_telemetry);
          };
          if (is_telemetry) channel->writable = [this] { pump(); };
          channel->disconnected = [this, is_telemetry](Channel& c) {
            auto& owner = is_telemetry ? telemetry_ : control_;
            if (owner.get() == &c) {
              owner.reset();
              if (!is_telemetry) {
                fault("controller_disconnected");
                if (telemetry_) { auto data = telemetry_; data->close(); }
              }
            }
          };
          channel->read();
        }
      }
      if (error != asio::error::operation_aborted) accept(is_telemetry);
    });
  }
  void schedule_tick() {
    if (engine_.state != "RUNNING") return;
    auto deadline = run_start_ + std::chrono::microseconds(
      (engine_.final_seq + 2LL) * 1000000LL / engine_.rate());
    tick_timer_.expires_at(deadline);
    tick_timer_.async_wait([this, deadline](const asio::error_code& error) {
      if (error || engine_.state != "RUNNING") return;
      if (Clock::now() - deadline > std::chrono::milliseconds(250)) {
        fault("scheduling_overrun"); return;
      }
      if (retained_.size() >= retained_limit) { fault("telemetry_retention_overflow"); return; }
      auto sample = engine_.tick();
      if (!sample) return;
      (*sample)["source_utc"] = utc_now();
      (*sample)["device_elapsed_s"] = elapsed();
      retained_.push_back(*sample);
      pump();
      schedule_tick();
    });
  }
  void check_lease() {
    lease_timer_.expires_after(std::chrono::milliseconds(200));
    lease_timer_.async_wait([this](const asio::error_code& error) {
      if (error) return;
      if (control_ && Clock::now() - last_control_ > std::chrono::seconds(5)) {
        fault("controller_lease_expired");
        auto connection = control_;
        connection->close();
      }
      check_lease();
    });
  }
 public:
  Server(asio::io_context& io, std::string id, const asio::ip::address& address)
    : io_(io), control_listener_(io, tcp::endpoint(address, 9000)),
      telemetry_listener_(io, tcp::endpoint(address, 9001)),
      tick_timer_(io), lease_timer_(io), instrument_(std::move(id)) {
    accept(false); accept(true); check_lease();
    std::cout << envelope("ready").dump() << std::endl;
  }
  void shutdown() {
    fault("engine_shutdown");
    if (control_) { auto c=control_; c->close(); }
    if (telemetry_) { auto c=telemetry_; c->close(); }
    control_listener_.close();
    telemetry_listener_.close();
    tick_timer_.cancel();
    lease_timer_.cancel();
    io_.stop();
  }
};
int main() {
  try {
    asio::io_context io;
    const auto* id = std::getenv("INSTRUMENT_ID");
    const auto* bind = std::getenv("INSTRUMENT_BIND_ADDRESS");
    Server server(io, id ? id : "sim-01", asio::ip::make_address(bind ? bind : "0.0.0.0"));
    asio::signal_set signals(io, SIGINT, SIGTERM);
    signals.async_wait([&](const asio::error_code&, int) { server.shutdown(); });
    io.run(); // Exactly one thread owns every engine field and callback.
  } catch (const std::exception& error) {
    std::cerr << "Instrument startup failed: " << error.what() << '\n';
    return 1;
  }
}
