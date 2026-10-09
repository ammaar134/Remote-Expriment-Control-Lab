#define DOCTEST_CONFIG_IMPLEMENT_WITH_MAIN
#include <doctest/doctest.h>
#include "engine.hpp"
using namespace lab;
Json recipe() {
  return {{"sample_rate_hz", 50}, {"seed", 7}, {"steps",
    {{{"setpoint", 0.8}, {"duration_ms", 40}},
     {{"setpoint", 0.2}, {"duration_ms", 40}}}}};
}
TEST_CASE("ticks, boundaries, determinism and completion") {
  Engine a, b;
  a.start("a", recipe(), true);
  b.start("b", recipe(), true);
  for (int seq = 0; seq < 4; ++seq) {
    auto x = a.tick(), y = b.tick();
    REQUIRE(x.has_value());
    CHECK(*x == *y);
    CHECK((*x)["seq"] == seq);
    CHECK((*x)["logical_s"].get<double>() == doctest::Approx((seq + 1) / 50.0));
    CHECK((*x)["setpoint"].get<double>() == doctest::Approx(seq < 2 ? 0.8 : 0.2));
  }
  CHECK(a.state == "COMPLETED");
  CHECK(a.output == 0);
  CHECK_FALSE(a.tick());
}
TEST_CASE("stop is applied, repeated stop and stale run are safe") {
  Engine e;
  e.start("a", recipe(), true);
  e.tick();
  e.stop("a");
  CHECK(e.state == "STOPPED");
  CHECK(e.output == 0);
  CHECK(e.final_seq == 0);
  CHECK_FALSE(e.tick());
  e.stop("a");
  e.start("b", recipe(), true);
  CHECK_THROWS_AS(e.stop("a"), Rejection);
  CHECK(e.state == "RUNNING");
  CHECK_THROWS_AS(e.start("c", recipe(), true), Rejection);
}
TEST_CASE("zero-sample stop, fault reset and completed stop") {
  Engine e;
  CHECK_THROWS_AS(e.start("a", recipe(), false), Rejection);
  e.start("a", recipe(), true);
  e.stop("a");
  CHECK(e.final_seq == -1);
  e.start("b", recipe(), true);
  e.fault("telemetry_overflow");
  CHECK(e.output == 0);
  CHECK_THROWS_AS(e.start("c", recipe(), true), Rejection);
  e.reset();
  e.start("c", recipe(), true);
  while (e.tick()) {}
  e.stop("c");
  CHECK(e.state == "COMPLETED");
}
TEST_CASE("invalid recipes are rejected before state changes") {
  Engine e;
  auto r = recipe();
  r["steps"][0]["setpoint"] = 2;
  CHECK_THROWS_AS(e.start("a", r, true), Rejection);
  CHECK(e.state == "IDLE");
  r = recipe(); r["steps"][0]["duration_ms"] = 21;
  CHECK_THROWS_AS(Recipe::parse(r), Rejection);
  r = recipe(); r["sample_rate_hz"] = 33;
  CHECK_THROWS_AS(Recipe::parse(r), Rejection);
  r = recipe(); r["seed"] = 0;
  CHECK_THROWS_AS(Recipe::parse(r), Rejection);
  r = recipe(); r["steps"][0]["duration_ms"] = 60000;
  CHECK_THROWS_AS(Recipe::parse(r), Rejection);
}
TEST_CASE("deduplication preserves responses and rejects conflicts") {
  CommandCache c;
  Json command{{"run_id", "a"}, {"value", 1}}, response{{"state", "RUNNING"}};
  CHECK_FALSE(c.lookup("one", command, 0, ""));
  c.remember("one", command, response, 0);
  CHECK(c.lookup("one", command, 2, "a") == response);
  CHECK(c.lookup("one", command, 200, "a") == response);
  auto changed = command; changed["value"] = 2;
  CHECK_THROWS_AS(c.lookup("one", changed, 2, "a"), Rejection);
  CHECK_FALSE(c.lookup("one", command, 201, ""));
}
TEST_CASE("idempotency storage is bounded and does not evict protected records") {
  CommandCache c;
  for (int i=0; i<256; ++i) {
    const auto id = std::to_string(i);
    Json command{{"run_id", "active"}, {"id", id}};
    CHECK_FALSE(c.lookup(id, command, 0, "active"));
    c.remember(id, command, Json::object(), 0);
  }
  CHECK_THROWS_AS(c.lookup("overflow", Json::object(), 200, "active"), Rejection);
  CHECK_FALSE(c.lookup("new", Json::object(), 201, ""));
}
