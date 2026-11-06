/**
 * Native C++ production-path replay for ground free-ray + local_update merge.
 *
 * Links libplan_env.so (NOT the Python model tests under adapters/.../scripts).
 * Verifies:
 *  1) Same-frame obstacle + ground free-ray → merged local_update → inflate covers
 *     OCCUPIED outside the ground-only AABB.
 *  2) Low-obstacle endpoints fed as depth OCC hits remain OCCUPIED after a
 *     subsequent free-ray pass (production post-filter cloud order).
 *
 * Usage (vln-rangercr10):
 *   rosrun plan_env test_map_pipeline_replay
 * Exit 0 on pass.
 */
#include <plan_env/sdf_map2d.h>
#include <plan_env/map_ros.h>
#include <plan_env/raycast2d.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <ros/ros.h>
#include <cmath>
#include <iostream>
#include <vector>

using apexnav_planner::SDFMap2D;
using Eigen::Vector2d;
using Eigen::Vector2i;
using Eigen::Vector3d;

static void setMapParams(ros::NodeHandle& nh)
{
  nh.setParam("is_real_world", true);
  nh.setParam("sdf_map/resolution", 0.05);
  nh.setParam("sdf_map/map_size_x", 10.0);
  nh.setParam("sdf_map/map_size_y", 10.0);
  nh.setParam("sdf_map/obstacles_inflation", 0.18);
  nh.setParam("sdf_map/local_bound", 3.0);
  nh.setParam("sdf_map/optimistic", false);
  nh.setParam("sdf_map/signed_dist", false);
  nh.setParam("sdf_map/ray_mode", 0);
  nh.setParam("sdf_map/p_hit", 0.70);
  nh.setParam("sdf_map/p_miss", 0.35);
  nh.setParam("sdf_map/p_min", 0.12);
  nh.setParam("sdf_map/p_max", 0.97);
  nh.setParam("sdf_map/p_occ", 0.80);
  nh.setParam("sdf_map/max_ray_length", 5.0);
  // MapROS still constructed; keep ground free off here — we inject clouds directly.
  nh.setParam("map_ros/ground_free_ray_enable", false);
  nh.setParam("map_ros/cx", 320.0);
  nh.setParam("map_ros/cy", 240.0);
  nh.setParam("map_ros/fx", 388.0);
  nh.setParam("map_ros/fy", 388.0);
  nh.setParam("map_ros/depth_filter_maxdist", 5.0);
  nh.setParam("map_ros/depth_filter_mindist", 0.5);
  nh.setParam("map_ros/depth_filter_margin", 1);
  nh.setParam("map_ros/filter_min_height", 0.28);
  nh.setParam("map_ros/filter_max_height", 1.18);
  nh.setParam("map_ros/k_depth_scaling_factor", 65535.0);
  nh.setParam("map_ros/skip_pixel", 1);
  nh.setParam("map_ros/frame_id", std::string("world"));
  nh.setParam("map_ros/virtual_ground_height", -0.34);
}

static pcl::PointCloud<pcl::PointXY>::Ptr cloudXY(const std::vector<Vector2d>& pts)
{
  pcl::PointCloud<pcl::PointXY>::Ptr c(new pcl::PointCloud<pcl::PointXY>());
  for (const auto& p : pts) {
    pcl::PointXY q;
    q.x = p.x();
    q.y = p.y();
    c->points.push_back(q);
  }
  return c;
}

int main(int argc, char** argv)
{
  ros::init(argc, argv, "test_map_pipeline_replay", ros::init_options::AnonymousName);
  ros::NodeHandle nh("~");
  setMapParams(nh);

  SDFMap2D map;
  map.initMap(nh);
  const Vector3d cam(0.0, 0.0, 0.88);
  std::vector<Vector2i> free_grids;
  bool ok = true;

  // ---------- Case 1: merge local_update ----------
  // Obstacle far +x; ground free endpoints near -x (disjoint boxes).
  // Multiple hits so log-odds crosses OCC threshold in one callback batch.
  std::vector<Vector2d> obst_pts;
  for (int i = 0; i < 8; ++i) obst_pts.push_back(Vector2d(1.50, 0.0));
  auto obst = cloudXY(obst_pts);
  auto ground = cloudXY({{-0.40, 0.10}, {-0.35, -0.05}});
  free_grids.clear();
  map.inputDepthCloud2D(obst, cam, free_grids);
  const bool after_depth = map.diagLocalUpdated();
  Eigen::Vector2i dmin, dmax, gmin, gmax, mmin, mmax;
  map.getLocalUpdateIndexBox(dmin, dmax);
  map.inputFreeRayCloud2D(ground, cam, free_grids);
  map.getLocalUpdateIndexBox(mmin, mmax);
  map.diagClearAndInflateLocalMap();
  const int occ_at_obst = map.getOccupancy(Vector2d(1.50, 0.0));
  const int inf_at_obst = map.getInflateOccupancy(Vector2d(1.50, 0.0));
  // Merged box must strictly contain depth-only box expansion toward ground.
  const bool merged_expands =
      (mmin.x() <= dmin.x() && mmax.x() >= dmax.x() && mmin.y() <= dmin.y() && mmax.y() >= dmax.y()) &&
      (mmin.x() < dmin.x() || mmax.x() > dmax.x() || mmin.y() < dmin.y() || mmax.y() > dmax.y());
  if (!after_depth || !merged_expands || occ_at_obst != SDFMap2D::OCCUPIED || inf_at_obst != 1) {
    std::cerr << "[FAIL] merge/inflate: after_depth=" << after_depth
              << " merged_expands=" << merged_expands << " occ=" << occ_at_obst
              << " inf=" << inf_at_obst << "\n";
    ok = false;
  } else {
    std::cout << "[PASS] same-frame local_update merge + inflate retains far obstacle\n";
  }

  // ---------- Case 2: low obstacles remain OCCUPIED after free-ray ----------
  // Fresh map instance to avoid cross-talk.
  SDFMap2D map2;
  map2.initMap(nh);
  std::vector<Vector2d> low_xy;
  for (double h_label : {0.05, 0.10, 0.20}) {
    for (int i = 0; i < 8; ++i)
      low_xy.push_back(Vector2d(0.80, h_label));  // distinct cells + multi-hit
  }
  auto low_cloud = cloudXY(low_xy);
  auto floor_free = cloudXY({{-0.30, 0.0}, {-0.25, 0.05}});
  free_grids.clear();
  map2.inputDepthCloud2D(low_cloud, cam, free_grids);
  map2.inputFreeRayCloud2D(floor_free, cam, free_grids);
  map2.diagClearAndInflateLocalMap();
  for (const auto& p : low_xy) {
    const int o = map2.getOccupancy(p);
    if (o != SDFMap2D::OCCUPIED) {
      std::cerr << "[FAIL] low obstacle at (" << p.x() << "," << p.y() << ") occ=" << o
                << " (want OCCUPIED) after free-ray\n";
      ok = false;
    }
  }
  if (ok)
    std::cout << "[PASS] 5/10/20cm-band endpoints stay OCCUPIED after free-ray update\n";

  std::cout << (ok ? "ALL_PASS\n" : "FAILED\n");
  return ok ? 0 : 1;
}
