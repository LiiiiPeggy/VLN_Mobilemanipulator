/**
 * Native A* replay: HY1 frozen local map + startup_prior A/B.
 *
 * Loads cells CSV (x,y,raw,inflate) from the frozen plan_seq_1_local_map dump,
 * runs production Astar2D::checkPointSafety / astarSearch under:
 *   A) startup_prior_mode=none
 *   B) startup_prior_mode=initial_footprint
 *
 * Does NOT rewrite occupancy as FREE; F0 is planning-query only.
 *
 * Usage:
 *   rosrun path_searching test_startup_prior_astar \
 *     _cells_csv:=.../cells.csv _candidates_csv:=.../candidates.csv \
 *     _chassis_x:=... _chassis_y:=... _yaw:=... \
 *     _half_l:=0.4557 _half_w:=0.30429 _out_json:=.../ab_compare.json
 */
#include <path_searching/astar2d.h>
#include <plan_env/sdf_map2d.h>
#include <plan_env/map_ros.h>
#include <plan_env/raycast2d.h>
#include <ros/ros.h>
#include <Eigen/Eigen>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using apexnav_planner::Astar2D;
using apexnav_planner::SDFMap2D;
using Eigen::Vector2d;
using Eigen::Vector2i;

struct Cell {
  double x, y;
  int raw, inflate;
};

struct Cand {
  double x, y;
};

static std::vector<Cell> loadCells(const std::string& path)
{
  std::vector<Cell> out;
  std::ifstream ifs(path);
  std::string line;
  while (std::getline(ifs, line)) {
    if (line.empty() || line[0] == '#')
      continue;
    Cell c;
    char comma;
    std::stringstream ss(line);
    if (!(ss >> c.x >> comma >> c.y >> comma >> c.raw >> comma >> c.inflate))
      continue;
    out.push_back(c);
  }
  return out;
}

static std::vector<Cand> loadCands(const std::string& path)
{
  std::vector<Cand> out;
  std::ifstream ifs(path);
  std::string line;
  while (std::getline(ifs, line)) {
    if (line.empty() || line[0] == '#')
      continue;
    Cand c;
    char comma;
    std::stringstream ss(line);
    if (!(ss >> c.x >> comma >> c.y))
      continue;
    out.push_back(c);
  }
  return out;
}

static void setBaseParams(ros::NodeHandle& nh, double map_size)
{
  nh.setParam("is_real_world", true);
  nh.setParam("sdf_map/resolution", 0.05);
  nh.setParam("sdf_map/map_size_x", map_size);
  nh.setParam("sdf_map/map_size_y", map_size);
  nh.setParam("sdf_map/obstacles_inflation", 0.18);
  nh.setParam("sdf_map/local_bound", 5.0);
  nh.setParam("sdf_map/optimistic", false);
  nh.setParam("sdf_map/signed_dist", false);
  nh.setParam("sdf_map/ray_mode", 0);
  nh.setParam("sdf_map/p_hit", 0.90);
  nh.setParam("sdf_map/p_miss", 0.48);
  nh.setParam("sdf_map/p_min", 0.10);
  nh.setParam("sdf_map/p_max", 0.98);
  nh.setParam("sdf_map/p_occ", 0.80);
  nh.setParam("sdf_map/max_ray_length", 4.99);
  nh.setParam("astar/resolution_astar", 0.1);
  nh.setParam("astar/lambda_heu", 1.0);
  // Silence MapROS camera params
  nh.setParam("map_ros/cx", 320.0);
  nh.setParam("map_ros/cy", 240.0);
  nh.setParam("map_ros/fx", 388.0);
  nh.setParam("map_ros/fy", 388.0);
  nh.setParam("map_ros/depth_filter_maxdist", 4.99);
  nh.setParam("map_ros/depth_filter_mindist", 0.5);
  nh.setParam("map_ros/depth_filter_margin", 2);
  nh.setParam("map_ros/filter_min_height", 0.28);
  nh.setParam("map_ros/filter_max_height", 1.18);
  nh.setParam("map_ros/k_depth_scaling_factor", 65535.0);
  nh.setParam("map_ros/skip_pixel", 1);
  nh.setParam("map_ros/frame_id", std::string("world"));
  nh.setParam("map_ros/virtual_ground_height", -0.34);
  nh.setParam("map_ros/ground_free_ray_enable", false);
}

static void loadFrozenMap(SDFMap2D& map, const std::vector<Cell>& cells)
{
  for (const auto& c : cells) {
    map.diagSetOccupancyState(Vector2d(c.x, c.y), c.raw, c.inflate);
  }
}

static bool occupancyUnchanged(SDFMap2D& map, const std::vector<Cell>& cells)
{
  for (const auto& c : cells) {
    const int occ = map.getOccupancy(Vector2d(c.x, c.y));
    const int inf = map.getInflateOccupancy(Vector2d(c.x, c.y));
    if (occ != c.raw || inf != c.inflate)
      return false;
  }
  return true;
}

struct RunResult {
  std::string mode;
  int n_reachable = 0;
  int n_candidates = 0;
  std::vector<Vector2d> best_path;
  double best_len = 0.0;
  Vector2d best_goal{0, 0};
  int path_prior_unknown_samples = 0;
  int path_outside_f0_unknown = 0;
  bool map_unchanged = false;
  // targeted checks
  bool f0_unk_allowed = false;
  bool outside_f0_unk_rejected = false;
  bool f0_occ_rejected = false;
  bool f0_inflate_rejected = false;
  bool f0_not_follow_motion = false;
  bool f0_cleared_on_clear = false;
};

static RunResult runMode(ros::NodeHandle& nh, const std::string& mode, const std::vector<Cell>& cells,
    const std::vector<Cand>& cands, const Vector2d& chassis, double yaw, double half_l,
    double half_w)
{
  RunResult rr;
  rr.mode = mode;
  nh.setParam("exploration/startup_prior_mode", mode);
  nh.setParam("exploration/startup_prior_half_length", half_l);
  nh.setParam("exploration/startup_prior_half_width", half_w);

  SDFMap2D::Ptr map(new SDFMap2D);
  map->initMap(nh);
  loadFrozenMap(*map, cells);

  Astar2D astar;
  astar.init(nh, map);
  astar.setCountRejects(true);
  astar.ensureStartupPrior(chassis, yaw);

  // Targeted unit checks via production checkPointSafety path (astarSearch edges).
  if (mode == "initial_footprint" && astar.hasStartupPrior()) {
    // Pick an UNKNOWN cell inside F0 and outside F0 from frozen dump.
    Vector2d unk_in(1e9, 1e9), unk_out(1e9, 1e9), occ_in(1e9, 1e9), inf_free(1e9, 1e9);
    bool have_in = false, have_out = false, have_occ = false, have_inf = false;
    for (const auto& c : cells) {
      Vector2d p(c.x, c.y);
      const bool in = astar.isInsideStartupPrior(p);
      if (c.raw == SDFMap2D::UNKNOWN && in && !have_in) {
        unk_in = p;
        have_in = true;
      }
      if (c.raw == SDFMap2D::UNKNOWN && !in && !have_out) {
        unk_out = p;
        have_out = true;
      }
      if (c.raw == SDFMap2D::OCCUPIED && in && !have_occ) {
        occ_in = p;
        have_occ = true;
      }
      if (c.inflate == 1 && c.raw != SDFMap2D::OCCUPIED && in && !have_inf) {
        inf_free = p;
        have_inf = true;
      }
    }
    // Force synthetic probes if needed for OCC/inflate inside F0
    if (!have_occ) {
      // Place a synthetic OCC at chassis center for reject check (then restore).
      map->diagSetOccupancyState(chassis, SDFMap2D::OCCUPIED, 0);
      occ_in = chassis;
      have_occ = true;
    }
    // Production checkPointSafety (via diag wrapper) — same predicate as search edges.
    if (have_in)
      rr.f0_unk_allowed = astar.diagCheckPointSafety(unk_in, Astar2D::SAFETY_MODE::NORMAL);
    if (have_out)
      rr.outside_f0_unk_rejected =
          !astar.diagCheckPointSafety(unk_out, Astar2D::SAFETY_MODE::NORMAL);
    if (have_occ)
      rr.f0_occ_rejected = !astar.diagCheckPointSafety(occ_in, Astar2D::SAFETY_MODE::NORMAL);
    // Restore chassis if we force-OCC'd it
    if (have_occ && (occ_in - chassis).norm() < 1e-6) {
      for (const auto& c : cells) {
        if (std::hypot(c.x - chassis.x(), c.y - chassis.y()) < 1e-4) {
          map->diagSetOccupancyState(chassis, c.raw, c.inflate);
          break;
        }
      }
    }
    // Inflate reject: force inflate on a FREE cell inside F0
    Vector2d inf_p = chassis;
    map->diagSetOccupancyState(inf_p, SDFMap2D::FREE, 1);
    rr.f0_inflate_rejected = !astar.diagCheckPointSafety(inf_p, Astar2D::SAFETY_MODE::NORMAL);
    // restore
    for (const auto& c : cells) {
      if (std::hypot(c.x - chassis.x(), c.y - chassis.y()) < 1e-4) {
        map->diagSetOccupancyState(chassis, c.raw, c.inflate);
        break;
      }
    }

    // F0 does not follow motion
    const Vector2d old_c = astar.getStartupPriorCenter();
    astar.ensureStartupPrior(chassis + Vector2d(1.0, 0.0), yaw);
    rr.f0_not_follow_motion = (astar.getStartupPriorCenter() - old_c).norm() < 1e-9;

    // clear removes F0
    astar.clearStartupPrior();
    rr.f0_cleared_on_clear = !astar.hasStartupPrior();
    // regenerate for path search
    astar.ensureStartupPrior(chassis, yaw);
  } else if (mode == "none") {
    rr.f0_unk_allowed = false;  // N/A expectation
    rr.outside_f0_unk_rejected = true;
    rr.f0_not_follow_motion = true;
    rr.f0_cleared_on_clear = true;
  }

  rr.n_candidates = static_cast<int>(cands.size());
  for (const auto& g : cands) {
    astar.reset();
    const int ret =
        astar.astarSearch(chassis, Vector2d(g.x, g.y), 0.25, 0.01, Astar2D::SAFETY_MODE::NORMAL);
    if (ret == Astar2D::REACH_END) {
      rr.n_reachable += 1;
      auto path = astar.getPath();
      const double len = Astar2D::pathLength(path);
      if (rr.best_path.empty() || len < rr.best_len) {
        rr.best_path = path;
        rr.best_len = len;
        rr.best_goal = Vector2d(g.x, g.y);
      }
    }
  }

  // Analyze safety-checked path samples.
  // ################################
  // ApexNav backtrack appends the raw frontier goal even when the search only
  // reached within success_dist (0.25 m); that terminal point is NOT passed
  // through checkPointSafety. Exclude the final node; count edges among
  // searched nodes only (indices 0..n-2 of path after reverse = all but last).
  // ################################
  if (rr.best_path.size() >= 2) {
    const size_t n_checked_nodes = rr.best_path.size() - 1;  // drop appended goal
    for (size_t i = 0; i + 1 < n_checked_nodes; ++i) {
      Vector2d a = rr.best_path[i];
      Vector2d b = rr.best_path[i + 1];
      Vector2d dir = b - a;
      const double len = dir.norm();
      if (len < 1e-9)
        continue;
      dir.normalize();
      for (double l = 0.0; l <= len + 1e-9; l += 0.025) {
        Vector2d p = a + l * dir;
        const int occ = map->getOccupancy(p);
        if (occ == SDFMap2D::UNKNOWN) {
          if (astar.isInsideStartupPrior(p))
            rr.path_prior_unknown_samples += 1;
          else
            rr.path_outside_f0_unknown += 1;
        }
      }
    }
  }

  rr.map_unchanged = occupancyUnchanged(*map, cells);
  return rr;
}

static void writeJson(const std::string& path, const RunResult& A, const RunResult& B,
    const Vector2d& chassis, double yaw, double half_l, double half_w)
{
  std::ofstream ofs(path);
  auto dump = [&](const RunResult& r) {
    ofs << "\"mode\":\"" << r.mode << "\"";
    ofs << ",\"n_reachable\":" << r.n_reachable;
    ofs << ",\"n_candidates\":" << r.n_candidates;
    ofs << ",\"best_len\":" << r.best_len;
    ofs << ",\"best_goal\":[" << r.best_goal.x() << "," << r.best_goal.y() << "]";
    ofs << ",\"path\":[";
    for (size_t i = 0; i < r.best_path.size(); ++i) {
      if (i)
        ofs << ",";
      ofs << "[" << r.best_path[i].x() << "," << r.best_path[i].y() << "]";
    }
    ofs << "]";
    ofs << ",\"path_prior_unknown_samples\":" << r.path_prior_unknown_samples;
    ofs << ",\"path_outside_f0_unknown\":" << r.path_outside_f0_unknown;
    ofs << ",\"map_unchanged\":" << (r.map_unchanged ? "true" : "false");
    ofs << ",\"checks\":{";
    ofs << "\"f0_unk_allowed\":" << (r.f0_unk_allowed ? "true" : "false");
    ofs << ",\"outside_f0_unk_rejected\":" << (r.outside_f0_unk_rejected ? "true" : "false");
    ofs << ",\"f0_occ_rejected\":" << (r.f0_occ_rejected ? "true" : "false");
    ofs << ",\"f0_inflate_rejected\":" << (r.f0_inflate_rejected ? "true" : "false");
    ofs << ",\"f0_not_follow_motion\":" << (r.f0_not_follow_motion ? "true" : "false");
    ofs << ",\"f0_cleared_on_clear\":" << (r.f0_cleared_on_clear ? "true" : "false");
    ofs << "}";
  };
  ofs << "{\"chassis\":[" << chassis.x() << "," << chassis.y() << "],\"yaw\":" << yaw
      << ",\"half_l\":" << half_l << ",\"half_w\":" << half_w << ",\"A\":{";
  dump(A);
  ofs << "},\"B\":{";
  dump(B);
  ofs << "}}\n";
}

int main(int argc, char** argv)
{
  ros::init(argc, argv, "test_startup_prior_astar", ros::init_options::AnonymousName);
  ros::NodeHandle nh("~");

  std::string cells_csv, cands_csv, out_json;
  double cx, cy, yaw, half_l, half_w, map_size;
  nh.param("cells_csv", cells_csv, std::string(""));
  nh.param("candidates_csv", cands_csv, std::string(""));
  nh.param("out_json", out_json, std::string("/tmp/startup_prior_ab.json"));
  nh.param("chassis_x", cx, 0.0);
  nh.param("chassis_y", cy, 0.0);
  nh.param("yaw", yaw, 0.0);
  nh.param("half_l", half_l, 0.4557);
  nh.param("half_w", half_w, 0.30429);
  nh.param("map_size", map_size, 80.0);

  if (cells_csv.empty() || cands_csv.empty()) {
    std::cerr << "[FAIL] need ~cells_csv and ~candidates_csv\n";
    return 2;
  }
  auto cells = loadCells(cells_csv);
  auto cands = loadCands(cands_csv);
  if (cells.empty() || cands.empty()) {
    std::cerr << "[FAIL] empty cells/cands\n";
    return 2;
  }
  std::cout << "[INFO] cells=" << cells.size() << " cands=" << cands.size() << "\n";

  setBaseParams(nh, map_size);
  Vector2d chassis(cx, cy);

  RunResult A = runMode(nh, "none", cells, cands, chassis, yaw, half_l, half_w);
  RunResult B =
      runMode(nh, "initial_footprint", cells, cands, chassis, yaw, half_l, half_w);

  writeJson(out_json, A, B, chassis, yaw, half_l, half_w);

  std::cout << "[A none] reachable=" << A.n_reachable << "/" << A.n_candidates
            << " best_len=" << A.best_len << " map_unchanged=" << A.map_unchanged << "\n";
  std::cout << "[B initial_footprint] reachable=" << B.n_reachable << "/" << B.n_candidates
            << " best_len=" << B.best_len
            << " prior_unk_samples=" << B.path_prior_unknown_samples
            << " outside_f0_unk=" << B.path_outside_f0_unknown
            << " map_unchanged=" << B.map_unchanged << "\n";
  std::cout << "[B checks] f0_unk_allowed=" << B.f0_unk_allowed
            << " outside_rejected=" << B.outside_f0_unk_rejected
            << " occ_rej=" << B.f0_occ_rejected << " inf_rej=" << B.f0_inflate_rejected
            << " no_follow=" << B.f0_not_follow_motion
            << " cleared=" << B.f0_cleared_on_clear << "\n";
  std::cout << "[OUT] " << out_json << "\n";

  bool ok = B.map_unchanged && A.map_unchanged && B.outside_f0_unk_rejected &&
            B.f0_inflate_rejected && B.f0_not_follow_motion && B.f0_cleared_on_clear &&
            B.path_outside_f0_unknown == 0;
  if (B.n_reachable > 0)
    ok = ok && B.f0_unk_allowed;
  // A expected: typically 0 reachable on HY1 freeze
  if (!ok) {
    std::cerr << "[FAIL] validation checks\n";
    return 1;
  }
  std::cout << "[PASS]\n";
  return 0;
}
