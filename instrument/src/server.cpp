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
    return value;
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
        response["engine_version"] = "0.1.0";
        channel.send(response);
        return;
      }
      if (telemetry) throw lab::Rejection("INVALID_MESSAGE", "Telemetry is receive-only in Phase 1");
      if (request.value("boot_id", "") != boot_)
        throw lab::Rejection("STALE_BOOT", "Boot identity mismatch");
      last_control_ = Clock::now();
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
          engine_.start(identifier(request, "run_id"), request.at("recipe"),
                        telemetry_ && telemetry_->ready);
          run_start_ = Clock::now();
          schedule_tick();
        } else if (type == "stop") {
          engine_.stop(identifier(request, "run_id"));
          tick_timer_.cancel();
        } else engine_.reset();
        response["ok"] = true;
        response["applied"] = true;
        response["status"] = observed();
      } catch (const lab::Rejection& error) {
        response["ok"] = false;
        response["error"] = {{"code", error.code}, {"message", error.what()}};
        response["status"] = observed();
      }
      cache_.remember(id, request, response, elapsed());
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
          channel->disconnected = [this, is_telemetry](Channel& c) {
            auto& owner = is_telemetry ? telemetry_ : control_;
            if (owner.get() == &c) {
              owner.reset();
              fault(is_telemetry ? "telemetry_disconnected" : "controller_disconnected");
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
      auto sample = engine_.tick();
      if (!sample) return;
      (*sample)["source_utc"] = utc_now();
      (*sample)["device_elapsed_s"] = elapsed();
      Json frame = envelope("samples");
      frame["run_id"] = engine_.run_id;
      frame["samples"] = Json::array({*sample});
      if (!telemetry_ || !telemetry_->send(frame)) {
        fault("telemetry_overflow"); return;
      }
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
