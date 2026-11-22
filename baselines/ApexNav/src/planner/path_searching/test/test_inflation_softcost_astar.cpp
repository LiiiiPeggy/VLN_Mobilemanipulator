/**
 * Offline P0/P1/P2 A* on a frozen plan_seq local_map.
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

struct Cell { double x, y; int raw, inflate; };
struct Cand { double x, y; };

static std::vector<Cell> loadCells(const std::string& path) {
  std::vector<Cell> out; std::ifstream ifs(path); std::string line;
  while (std::getline(ifs, line)) {
    if (line.empty() || line[0] == '#') continue;
    Cell c; char comma; std::stringstream ss(line);
    if (!(ss >> c.x >> comma >> c.y >> comma >> c.raw >> comma >> c.inflate)) continue;
    out.push_back(c);
  }
  return out;
}
static std::vector<Cand> loadCands(const std::string& path) {
  std::vector<Cand> out; std::ifstream ifs(path); std::string line;
  while (std::getline(ifs, line)) {
    if (line.empty() || line[0] == '#') continue;
    Cand c; char comma; std::stringstream ss(line);
    if (!(ss >> c.x >> comma >> c.y)) continue;
    out.push_back(c);
  }
  return out;
}
static void setParams(ros::NodeHandle& nh, double map_size, double inflate_m, double soft_R, double soft_w) {
  nh.setParam("is_real_world", true);
  nh.setParam("sdf_map/resolution", 0.05);
  nh.setParam("sdf_map/map_size_x", map_size);
  nh.setParam("sdf_map/map_size_y", map_size);
  nh.setParam("sdf_map/obstacles_inflation", inflate_m);
  nh.setParam("sdf_map/lock_obstacles_inflation", true);
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
  nh.setParam("astar/soft_cost_range_m", soft_R);
  nh.setParam("astar/soft_cost_weight", soft_w);
  nh.setParam("map_ros/cx", 320.0); nh.setParam("map_ros/cy", 240.0);
  nh.setParam("map_ros/fx", 388.0); nh.setParam("map_ros/fy", 388.0);
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

int main(int argc, char** argv) {
  ros::init(argc, argv, "test_inflation_softcost_astar", ros::init_options::AnonymousName);
  ros::NodeHandle nh("~");
  std::string cells_csv, cands_csv, out_json, prior_mode;
  double cx, cy, yaw, half_l, half_w, expand_m, map_size, inflate_m, soft_R, soft_w;
  nh.param("cells_csv", cells_csv, std::string(""));
  nh.param("candidates_csv", cands_csv, std::string(""));
  nh.param("out_json", out_json, std::string("/tmp/inflation_softcost.json"));
  nh.param("chassis_x", cx, 0.0); nh.param("chassis_y", cy, 0.0); nh.param("yaw", yaw, 0.0);
  nh.param("half_l", half_l, 0.4557); nh.param("half_w", half_w, 0.30429);
  nh.param("expand_m", expand_m, 0.3); nh.param("map_size", map_size, 80.0);
  nh.param("inflate_m", inflate_m, 0.18); nh.param("soft_R", soft_R, 0.0); nh.param("soft_w", soft_w, 0.0);
  nh.param("startup_prior_mode", prior_mode, std::string("initial_footprint"));
  if (cells_csv.empty() || cands_csv.empty()) { std::cerr << "[FAIL] need csv\n"; return 2; }
  auto cells = loadCells(cells_csv); auto cands = loadCands(cands_csv);
  if (cells.empty()) { std::cerr << "[FAIL] empty cells\n"; return 2; }
  setParams(nh, map_size, inflate_m, soft_R, soft_w);
  nh.setParam("exploration/startup_prior_mode", prior_mode);
  nh.setParam("exploration/startup_prior_half_length", half_l);
  nh.setParam("exploration/startup_prior_half_width", half_w);
  nh.setParam("exploration/startup_prior_expand_m", expand_m);
  double xmin=1e9,ymin=1e9,xmax=-1e9,ymax=-1e9;
  for (const auto& c: cells){ xmin=std::min(xmin,c.x); ymin=std::min(ymin,c.y); xmax=std::max(xmax,c.x); ymax=std::max(ymax,c.y);} 
  const double pad = inflate_m + 0.25;
  Vector2d bmin(xmin-pad, ymin-pad), bmax(xmax+pad, ymax+pad);
  SDFMap2D::Ptr map(new SDFMap2D);
  map->initMap(nh);
  map->diagSetLocalBounds(bmin, bmax);
  for (const auto& c: cells) map->diagSetOccupancyState(Vector2d(c.x,c.y), c.raw, 0);
  map->diagClearAndInflateLocalMap();
  map->updateESDFMap();
  Astar2D astar; astar.init(nh, map);
  Vector2d chassis(cx, cy);
  if (prior_mode == "initial_footprint") astar.ensureStartupPrior(chassis, yaw);
  int n_reachable=0, n_no_path=0;
  std::vector<Vector2d> best_path; double best_len=0; Vector2d best_goal(0,0);
  for (const auto& g: cands) {
    astar.reset();
    const int ret = astar.astarSearch(chassis, Vector2d(g.x,g.y), 0.25, 1.0, Astar2D::SAFETY_MODE::NORMAL);
    if (ret == Astar2D::REACH_END) {
      n_reachable++; auto path=astar.getPath(); double len=Astar2D::pathLength(path);
      if (best_path.empty() || len < best_len) { best_path=path; best_len=len; best_goal=Vector2d(g.x,g.y); }
    } else n_no_path++;
  }
  double min_d_obs=1e9;
  for (const auto& p: best_path) { double d=map->getDistanceToKnownObstacle(p); if (d>=0) min_d_obs=std::min(min_d_obs,d); }
  if (best_path.empty()) min_d_obs=-1.0;
  std::ofstream ofs(out_json);
  ofs << "{\"inflate_m\":"<<inflate_m<<",\"soft_R\":"<<soft_R<<",\"soft_w\":"<<soft_w
      <<",\"n_candidates\":"<<cands.size()<<",\"n_reachable\":"<<n_reachable
      <<",\"n_no_path\":"<<n_no_path<<",\"best_len\":"<<best_len
      <<",\"best_goal\":["<<best_goal.x()<<","<<best_goal.y()<<"]"
      <<",\"min_dist_to_inflate_boundary_m\":"<<min_d_obs<<",\"path\":[";
  for (size_t i=0;i<best_path.size();++i){ if(i) ofs<<","; ofs<<"["<<best_path[i].x()<<","<<best_path[i].y()<<"]"; }
  ofs << "]}\n";
  std::cout << "[OK] reachable="<<n_reachable<<"/"<<cands.size()<<" best_len="<<best_len
            <<" min_d_obs="<<min_d_obs<<" -> "<<out_json<<"\n";
  return 0;
}
