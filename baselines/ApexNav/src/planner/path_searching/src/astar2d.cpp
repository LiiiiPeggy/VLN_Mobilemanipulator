#include <path_searching/astar2d.h>
#include <sstream>

using namespace std;
using namespace Eigen;

namespace apexnav_planner {
Astar2D::~Astar2D()
{
  for (int i = 0; i < allocate_num_; i++) delete path_node_pool_[i];
}

void Astar2D::init(ros::NodeHandle& nh, const SDFMap2D::Ptr& sdf_map)
{
  // Free existing node pool before reallocation to prevent leak on re-init
  for (auto* node : path_node_pool_) {
    delete node;
  }
  path_node_pool_.clear();

  nh.param("astar/resolution_astar", resolution_, -1.0);
  nh.param("astar/lambda_heu", lambda_heu_, -1.0);
  allocate_num_ = 1000000;

  this->sdf_map_ = sdf_map;

  /* ---------- map params ---------- */
  this->inv_resolution_ = 1.0 / resolution_;
  sdf_map_->getRegion(origin_, map_size_2d_);
  cout << "origin_: " << origin_.transpose() << endl;
  cout << "map size: " << map_size_2d_.transpose() << endl;

  path_node_pool_.resize(allocate_num_);
  for (int i = 0; i < allocate_num_; i++) path_node_pool_[i] = new Node2D;
  use_node_num_ = 0;
  iter_num_ = 0;
  early_terminate_cost_ = 0.0;
}

void Astar2D::reset()
{
  open_set_map_.clear();
  close_set_map_.clear();
  path_nodes_.clear();

  std::priority_queue<Node2DPtr, std::vector<Node2DPtr>, NodeComparator2D> empty_queue;
  open_set_.swap(empty_queue);
  for (int i = 0; i < use_node_num_; i++) {
    path_node_pool_[i]->parent = nullptr;
  }
  use_node_num_ = 0;
  iter_num_ = 0;
}

void Astar2D::setResolution(const double& res)
{
  resolution_ = res;
  this->inv_resolution_ = 1.0 / resolution_;
}

int Astar2D::astarSearch(const Eigen::Vector2d& start_pt, const Eigen::Vector2d& end_pt,
    double success_dist, double max_time, int safety_mode)
{
  if (count_rejects_)
    reject_stats_.reset();
  last_return_code_ = 0;
  last_search_time_ = 0.0;

  Node2DPtr cur_node = path_node_pool_[0];
  cur_node->parent = nullptr;
  cur_node->position = start_pt;
  posToIndex(start_pt, cur_node->index);
  cur_node->g_score = 0.0;
  cur_node->f_score = lambda_heu_ * getDiagHeu(cur_node->position, end_pt);

  Eigen::Vector2i end_index;
  posToIndex(end_pt, end_index);

  open_set_.push(cur_node);
  open_set_map_.insert(make_pair(cur_node->index, cur_node));
  use_node_num_ += 1;

  const auto t1 = ros::Time::now();

  /* ---------- search loop ---------- */
  while (!open_set_.empty()) {
    cur_node = open_set_.top();
    bool reach_end =
        abs(cur_node->index(0) - end_index(0)) <= 1 && abs(cur_node->index(1) - end_index(1)) <= 1;
    if ((cur_node->position - end_pt).norm() < success_dist)
      reach_end = true;
    if (reach_end) {
      backtrack(cur_node, end_pt);
      // ################################
      // Counterfactual on SELECTED PATH edges only (not "start is UNKNOWN").
      // An edge is exempted iff its destination is within 0.25 m of start
      // (same gate as search). Check dest + intermediate samples silently.
      // ################################
      if (count_rejects_ && path_nodes_.size() >= 2) {
        for (size_t i = 0; i + 1 < path_nodes_.size(); ++i) {
          const Eigen::Vector2d& a = path_nodes_[i];
          const Eigen::Vector2d& b = path_nodes_[i + 1];
          if ((b - start_pt).norm() > 0.25)
            continue;
          reject_stats_.path_exempted_edges += 1;
          if (edgeWouldFailSafetySilent(a, b, safety_mode)) {
            reject_stats_.path_exempted_edges_would_fail += 1;
            reject_stats_.path_relied_near_start_exemption = 1;
          }
        }
      }
      last_search_time_ = (ros::Time::now() - t1).toSec();
      last_return_code_ = REACH_END;
      return REACH_END;
    }

    // Early termination if time up
    if ((ros::Time::now() - t1).toSec() > max_time) {
      early_terminate_cost_ = cur_node->g_score + getDiagHeu(cur_node->position, end_pt);
      if (count_rejects_)
        reject_stats_.time_budget += 1;
      last_search_time_ = (ros::Time::now() - t1).toSec();
      last_return_code_ = NO_PATH;
      return NO_PATH;
    }

    open_set_.pop();
    open_set_map_.erase(cur_node->index);
    close_set_map_.insert(make_pair(cur_node->index, 1));
    iter_num_ += 1;

    Eigen::Vector2d cur_pos = cur_node->position;
    Eigen::Vector2d nbr_pos;

    std::vector<Eigen::Vector2d> steps = generateSteps(cur_pos);
    for (auto step : steps) {
      nbr_pos = cur_pos + step;

      // Skip safety raycast if still near start to avoid immediate termination
      // ################################
      // Observe-only counters for the 0.25 m exemption (behavior unchanged).
      // ################################
      const double dist_from_start = (nbr_pos - start_pt).norm();
      if (dist_from_start > 0.25) {
        // Check safety
        if (!checkPointSafety(nbr_pos, safety_mode))
          continue;

        bool safe = true;
        Vector2d dir = nbr_pos - cur_pos;
        double len = dir.norm();
        dir.normalize();
        for (double l = 0.025; l < len; l += 0.025) {
          Vector2d ckpt = cur_pos + l * dir;
          if (!checkPointSafety(ckpt, safety_mode)) {
            safe = false;
            break;
          }
        }
        if (!safe)
          continue;
      } else if (count_rejects_) {
        reject_stats_.near_start_skip_accepted += 1;
        // Silent: do not pollute occupied/inflate/unknown reject tallies.
        if (!checkPointSafetySilent(nbr_pos, safety_mode) ||
            edgeWouldFailSafetySilent(cur_pos, nbr_pos, safety_mode))
          reject_stats_.near_start_skip_would_fail += 1;
      }

      // Check not in close set
      Eigen::Vector2i nbr_idx;
      posToIndex(nbr_pos, nbr_idx);
      if (close_set_map_.find(nbr_idx) != close_set_map_.end())
        continue;

      Node2DPtr neighbor;
      double tmp_g_score = step.norm() + cur_node->g_score;
      auto node_iter = open_set_map_.find(nbr_idx);
      if (node_iter == open_set_map_.end()) {
        neighbor = path_node_pool_[use_node_num_];
        use_node_num_ += 1;
        if (use_node_num_ == allocate_num_) {
          cout << "run out of node pool." << endl;
          if (count_rejects_)
            reject_stats_.node_pool += 1;
          last_search_time_ = (ros::Time::now() - t1).toSec();
          last_return_code_ = NO_PATH;
          return NO_PATH;
        }
        neighbor->index = nbr_idx;
        neighbor->position = nbr_pos;
      }
      else if (tmp_g_score < node_iter->second->g_score) {
        neighbor = node_iter->second;
      }
      else
        continue;

      neighbor->parent = cur_node;
      neighbor->g_score = tmp_g_score;
      neighbor->f_score = tmp_g_score + lambda_heu_ * getDiagHeu(nbr_pos, end_pt);
      open_set_.push(neighbor);
      open_set_map_[nbr_idx] = neighbor;
    }
  }
  last_search_time_ = (ros::Time::now() - t1).toSec();
  last_return_code_ = NO_PATH;
  return NO_PATH;
}

std::vector<Eigen::Vector2d> Astar2D::generateSteps(Eigen::Vector2d pos)
{
  vector<Eigen::Vector2d> steps;

  // Normal Astar Step
  // for (double dx = -resolution_; dx <= resolution_ + 1e-3; dx += resolution_)
  //   for (double dy = -resolution_; dy <= resolution_ + 1e-3; dy += resolution_) {
  //     Eigen::Vector2d step;
  //     step << dx, dy;
  //     if (step.norm() < 1e-3)
  //       continue;
  //     steps.push_back(step);
  //   }

  // Habitat-like stepping (12 directions)
  const double step_length = 0.25;
  const double angle_increment = M_PI / 6;

  for (int i = 0; i < 12; ++i) {
    double angle = i * angle_increment;
    Eigen::Vector2d step(step_length * cos(angle), step_length * sin(angle));
    steps.push_back(step);
  }
  return steps;
}

double Astar2D::getDiagHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2)
{
  double dx = fabs(x1(0) - x2(0));
  double dy = fabs(x1(1) - x2(1));
  double tie_breaker = 1.0 + 1e-6 * (dx + dy);
  // Diagonal distance heuristic for 2D
  return tie_breaker * (sqrt(2.0) * min(dx, dy) + abs(dx - dy));
}

double Astar2D::getManhHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2)
{
  double dx = fabs(x1(0) - x2(0));
  double dy = fabs(x1(1) - x2(1));
  double tie_breaker = 1.0 + 1e-6 * (dx + dy);
  // Manhattan distance heuristic for 2D
  return tie_breaker * (dx + dy);
}

double Astar2D::getEuclHeu(const Eigen::Vector2d& x1, const Eigen::Vector2d& x2)
{
  double dx = fabs(x1(0) - x2(0));
  double dy = fabs(x1(1) - x2(1));
  double tie_breaker = 1.0 + 1e-6 * (dx + dy);
  // Euclidean distance heuristic for 2D
  return tie_breaker * (x2 - x1).norm();
}

void Astar2D::backtrack(const Node2DPtr& end_node, const Eigen::Vector2d& end)
{
  path_nodes_.push_back(end);
  path_nodes_.push_back(end_node->position);
  Node2DPtr cur_node = end_node;
  while (cur_node->parent != nullptr) {
    cur_node = cur_node->parent;
    path_nodes_.push_back(cur_node->position);
  }
  reverse(path_nodes_.begin(), path_nodes_.end());
}

std::vector<Eigen::Vector2d> Astar2D::getVisited()
{
  vector<Eigen::Vector2d> visited;
  for (int i = 0; i < use_node_num_; ++i) visited.push_back(path_node_pool_[i]->position);
  return visited;
}

void Astar2D::posToIndex(const Eigen::Vector2d& pt, Eigen::Vector2i& idx)
{
  idx = ((pt - origin_) * inv_resolution_).array().floor().cast<int>();
}

std::vector<Eigen::Vector2d> Astar2D::getPath()
{
  return path_nodes_;
}

double Astar2D::pathLength(const vector<Eigen::Vector2d>& path)
{
  double length = 0.0;
  if (path.size() < 2)
    return length;
  for (int i = 0; i < (int)path.size() - 1; ++i) length += (path[i + 1] - path[i]).norm();
  return length;
}

bool Astar2D::checkPointSafetySilent(const Eigen::Vector2d& pos, int safety_mode) const
{
  if (!sdf_map_->isInMap(pos))
    return false;
  if (safety_mode == SAFETY_MODE::EXTREME)
    return true;
  const auto occ = sdf_map_->getOccupancy(pos);
  if (sdf_map_->getInflateOccupancy(pos) == 1)
    return false;
  if (occ == SDFMap2D::OCCUPIED)
    return false;
  if (occ == SDFMap2D::UNKNOWN && safety_mode == SAFETY_MODE::NORMAL)
    return false;
  return true;
}

bool Astar2D::edgeWouldFailSafetySilent(const Eigen::Vector2d& from, const Eigen::Vector2d& to,
    int safety_mode) const
{
  if (!checkPointSafetySilent(to, safety_mode))
    return true;
  Eigen::Vector2d dir = to - from;
  const double len = dir.norm();
  if (len < 1e-9)
    return false;
  dir.normalize();
  for (double l = 0.025; l < len; l += 0.025) {
    if (!checkPointSafetySilent(from + l * dir, safety_mode))
      return true;
  }
  return false;
}

bool Astar2D::checkPointSafety(const Eigen::Vector2d& pos, int safety_mode)
{
  // Outside map bounds is always unsafe
  if (!sdf_map_->isInMap(pos)) {
    if (count_rejects_)
      reject_stats_.out_of_bounds += 1;
    return false;
  }

  // EXTREME: allow any position inside the map (bypass occupancy checks)
  if (safety_mode == SAFETY_MODE::EXTREME)
    return true;

  // Occupancy checks
  const auto occ = sdf_map_->getOccupancy(pos);
  // If inflated occupancy marks collision, or cell is definitely occupied -> unsafe
  if (sdf_map_->getInflateOccupancy(pos) == 1) {
    if (count_rejects_)
      reject_stats_.inflate += 1;
    return false;
  }
  if (occ == SDFMap2D::OCCUPIED) {
    if (count_rejects_)
      reject_stats_.occupied += 1;
    return false;
  }

  // In NORMAL mode, treat unknown as unsafe. In OPTIMISTIC, unknown is allowed.
  if (occ == SDFMap2D::UNKNOWN && safety_mode == SAFETY_MODE::NORMAL) {
    if (count_rejects_)
      reject_stats_.unknown += 1;
    return false;
  }

  return true;
}
}  // namespace apexnav_planner
