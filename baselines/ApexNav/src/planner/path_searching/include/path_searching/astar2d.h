#ifndef _ASTAR2D_H
#define _ASTAR2D_H

#include <Eigen/Eigen>
#include <iostream>
#include <map>
#include <ros/console.h>
#include <ros/ros.h>
#include <string>
#include <unordered_map>
#include <plan_env/sdf_map2d.h>
#include <boost/functional/hash.hpp>
#include <queue>
#include <path_searching/matrix_hash.h>

namespace apexnav_planner {
class Node2D {
public:
  Eigen::Vector2i index;
  Eigen::Vector2d position;
  double g_score, f_score;
  Node2D* parent;

  Node2D() : index(0, 0), position(0.0, 0.0), g_score(0.0), f_score(0.0), parent(nullptr)
  {
  }
  ~Node2D() = default;
};
typedef Node2D* Node2DPtr;

class NodeComparator2D {
public:
  bool operator()(Node2DPtr node1, Node2DPtr node2)
  {
    return node1->f_score > node2->f_score;
  }
};

// ################################
// Optional reject counters for gated planner diagnostics. Counting does NOT
// change search decisions; "inferred from neighbor rejects" ≠ search return code.
// ################################
struct AstarRejectStats {
  int occupied = 0;
  int inflate = 0;
  int unknown = 0;
  int out_of_bounds = 0;
  int time_budget = 0;
  int node_pool = 0;
  // ################################
  // Observe-only: 0.25 m near-start safety skip (does NOT change the skip).
  // Counterfactual safety uses a silent checker — must NOT increment occupied/
  // inflate/unknown reject counts.
  // path_relied_near_start_exemption: selected path has an exempted EDGE
  //   (destination within 0.25 m of start) whose nbr or intermediate samples
  //   would fail safety. Does NOT fire solely because the start cell is UNKNOWN.
  // ################################
  int near_start_skip_accepted = 0;
  int near_start_skip_would_fail = 0;
  int path_exempted_edges = 0;
  int path_exempted_edges_would_fail = 0;
  int path_relied_near_start_exemption = 0;
  void reset()
  {
    occupied = inflate = unknown = out_of_bounds = time_budget = node_pool = 0;
    near_start_skip_accepted = near_start_skip_would_fail = 0;
    path_exempted_edges = path_exempted_edges_would_fail = 0;
    path_relied_near_start_exemption = 0;
  }
};

class Astar2D {
public:
  Astar2D() = default;
  ~Astar2D();
  enum { REACH_END = 1, NO_PATH = 2 };
  enum SAFETY_MODE { NORMAL = 0, OPTIMISTIC = 1, EXTREME = 2 };
  void init(ros::NodeHandle& nh, const SDFMap2D::Ptr& sdf_map);
  void reset();
  int astarSearch(const Eigen::Vector2d& start_pt, const Eigen::Vector2d& end_pt,
      double success_dist = 0.1, double max_time = 0.01, int safety_mode = SAFETY_MODE::NORMAL);
  void setResolution(const double& res);
  static double pathLength(const std::vector<Eigen::Vector2d>& path);
  std::vector<Eigen::Vector2d> generateSteps(Eigen::Vector2d pos);

  std::vector<Eigen::Vector2d> getPath();
  std::vector<Eigen::Vector2d> getVisited();
  double getEarlyTerminateCost();
  void setCountRejects(bool enable) { count_rejects_ = enable; }
  const AstarRejectStats& getRejectStats() const { return reject_stats_; }
  int getLastReturnCode() const { return last_return_code_; }
  double getLastSearchTime() const { return last_search_time_; }
  int getUseNodeNum() const { return use_node_num_; }
  int getIterNum() const { return iter_num_; }

  double lambda_heu_;

private:
  void backtrack(const Node2DPtr& end_node, const Eigen::Vector2d& end);
  void posToIndex(const Eigen::Vector2d& pt, Eigen::Vector2i& idx);
  double getDiagHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2);
  double getManhHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2);
  double getEuclHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2);
  bool checkPointSafety(const Eigen::Vector2d& pos, int safety_mode);
  // ################################
  // Same predicates as checkPointSafety but never mutates reject_stats_.
  // ################################
  bool checkPointSafetySilent(const Eigen::Vector2d& pos, int safety_mode) const;
  bool edgeWouldFailSafetySilent(const Eigen::Vector2d& from, const Eigen::Vector2d& to,
      int safety_mode) const;

  // main data structure
  std::vector<Node2DPtr> path_node_pool_;
  int use_node_num_, iter_num_;
  std::priority_queue<Node2DPtr, std::vector<Node2DPtr>, NodeComparator2D> open_set_;
  std::unordered_map<Eigen::Vector2i, Node2DPtr, matrix_hash<Eigen::Vector2i>> open_set_map_;
  std::unordered_map<Eigen::Vector2i, int, matrix_hash<Eigen::Vector2i>> close_set_map_;
  std::vector<Eigen::Vector2d> path_nodes_;
  double early_terminate_cost_;

  SDFMap2D::Ptr sdf_map_;

  // parameter
  double margin_;
  int allocate_num_;
  double resolution_, inv_resolution_;
  Eigen::Vector2d map_size_2d_, origin_;

  // ################################
  bool count_rejects_ = false;
  AstarRejectStats reject_stats_;
  int last_return_code_ = 0;
  double last_search_time_ = 0.0;
  // ################################
};

}  // namespace apexnav_planner

#endif
