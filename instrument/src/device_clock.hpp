#pragma once
#include "engine.hpp"
#include <cmath>

namespace lab {
// A simulated civil clock, anchored to host UTC once, advanced by a local
// monotonic duration. Neither the operating-system clock nor tick scheduling moves.
class DeviceClock {
  double anchor_utc_ = 0, anchor_elapsed_ = 0, offset_ms_ = 0, drift_ppm_ = 0;
 public:
  void configure(const Json& value, double utc, double elapsed) {
    if (!value.is_object() || value.size() != 2 ||
        !value.contains("offset_ms") || !value.contains("drift_ppm") ||
        !value["offset_ms"].is_number() || !value["drift_ppm"].is_number())
      throw Rejection("INVALID_CLOCK", "Clock requires offset_ms and drift_ppm");
    const double offset = value["offset_ms"].get<double>();
    const double drift = value["drift_ppm"].get<double>();
    if (!std::isfinite(offset) || !std::isfinite(drift) ||
        std::abs(offset) > 5000 || std::abs(drift) > 10000)
      throw Rejection("INVALID_CLOCK", "Clock offset or drift outside educational bounds");
    anchor_utc_ = utc; anchor_elapsed_ = elapsed;
    offset_ms_ = offset; drift_ppm_ = drift;
  }
  double utc(double elapsed) const {
    return anchor_utc_ + offset_ms_ / 1000 +
      (elapsed - anchor_elapsed_) * (1 + drift_ppm_ / 1000000);
  }
};
} // namespace lab
