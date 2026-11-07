/**
 * Native C++ production-path replay for ground free-ray + local_update merge.
 *
 * Links libplan_env.so (NOT the Python model tests under adapters/.../scripts).
 *
 * Scope of cases:
 *  A) XY-only local_update merge replay (NO height filter / no MapROS classify):
 *     verifies same-frame obstacle+ground free-ray merge/inflate on SDFMap2D.
 *  B) XY-only low-obstacle retention after free-ray (Y is cell index, NOT height).
 *  C) 3D-keep-Z production path: real AGL z=5/10/20 cm obstacles mixed with
 *     planar ground, through MapROS voxel→classify→outlier→map update.
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

using apexnav_planner::MapROS;
using apexnav_planner::SDFMap2D;
using Eigen::Quaterniond;
using Eigen::Vector2d;
using Eigen::Vector2i;
using Eigen::Vector3d;

static void setMapParams(ros::NodeHandle& nh, bool ground_free)
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
  nh.setParam("map_ros/ground_free_ray_enable", ground_free);
  nh.setParam("map_ros/ground_free_max_agl", 0.03);
  nh.setParam("map_ros/ground_free_planar_radius", 0.12);
  nh.setParam("map_ros/ground_free_planar_z_tol", 0.02);
  nh.setParam("map_ros/ground_free_planar_min_neighbors", 5);
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

static void addClusterXYZ(pcl::PointCloud<pcl::PointXYZ>::Ptr cloud, double x0, double y0,
    double z, int n_side, double spacing)
{
  for (int ix = 0; ix < n_side; ++ix) {
    for (int iy = 0; iy < n_side; ++iy) {
      pcl::PointXYZ p;
      p.x = static_cast<float>(x0 + (ix - n_side / 2) * spacing);
      p.y = static_cast<float>(y0 + (iy - n_side / 2) * spacing);
      p.z = static_cast<float>(z);
      cloud->points.push_back(p);
    }
  }
}

int main(int argc, char** argv)
{
  ros::init(argc, argv, "test_map_pipeline_replay", ros::init_options::AnonymousName);
  ros::NodeHandle nh("~");
  setMapParams(nh, /*ground_free=*/false);

  SDFMap2D map;
  map.initMap(nh);
  const Vector3d cam(0.0, 0.0, 0.88);
  std::vector<Vector2i> free_grids;
  bool ok = true;

  // ---------- Case A: XY-only merge local_update (scope: no height filter) ----------
  std::cout << "[SCOPE] Case A = XY-only SDFMap2D local_update merge/inflate "
               "(bypasses MapROS height classify)\n";
  std::vector<Vector2d> obst_pts;
  for (int i = 0; i < 8; ++i) obst_pts.push_back(Vector2d(1.50, 0.0));
  auto obst = cloudXY(obst_pts);
  auto ground = cloudXY({{-0.40, 0.10}, {-0.35, -0.05}});
  free_grids.clear();
  map.inputDepthCloud2D(obst, cam, free_grids);
  const bool after_depth = map.diagLocalUpdated();
  Eigen::Vector2i dmin, dmax, mmin, mmax;
  map.getLocalUpdateIndexBox(dmin, dmax);
  map.inputFreeRayCloud2D(ground, cam, free_grids);
  map.getLocalUpdateIndexBox(mmin, mmax);
  map.diagClearAndInflateLocalMap();
  const int occ_at_obst = map.getOccupancy(Vector2d(1.50, 0.0));
  const int inf_at_obst = map.getInflateOccupancy(Vector2d(1.50, 0.0));
  const bool merged_expands =
      (mmin.x() <= dmin.x() && mmax.x() >= dmax.x() && mmin.y() <= dmin.y() && mmax.y() >= dmax.y()) &&
      (mmin.x() < dmin.x() || mmax.x() > dmax.x() || mmin.y() < dmin.y() || mmax.y() > dmax.y());
  if (!after_depth || !merged_expands || occ_at_obst != SDFMap2D::OCCUPIED || inf_at_obst != 1) {
    std::cerr << "[FAIL] CaseA merge/inflate: after_depth=" << after_depth
              << " merged_expands=" << merged_expands << " occ=" << occ_at_obst
              << " inf=" << inf_at_obst << "\n";
    ok = false;
  } else {
    std::cout << "[PASS] CaseA XY-only same-frame local_update merge + inflate\n";
  }

  // ---------- Case B: XY-only low-obstacle retention (Y≠height) ----------
  std::cout << "[SCOPE] Case B = XY-only: endpoints labeled 5/10/20cm use Y as distinct "
               "cell index, NOT metric height; MapROS classify not exercised\n";
  SDFMap2D map2;
  map2.initMap(nh);
  std::vector<Vector2d> low_xy;
  for (double h_label : {0.05, 0.10, 0.20}) {
    for (int i = 0; i < 8; ++i)
      low_xy.push_back(Vector2d(0.80, h_label));
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
      std::cerr << "[FAIL] CaseB XY-low at (" << p.x() << "," << p.y() << ") occ=" << o
                << " (want OCCUPIED) after free-ray\n";
      ok = false;
    }
  }
  if (ok)
    std::cout << "[PASS] CaseB XY-only labeled endpoints stay OCCUPIED after free-ray\n";

  // ---------- Case C: real Z AGL through MapROS production filter ----------
  std::cout << "[SCOPE] Case C = 3D-keep-Z production path via MapROS::diagProcessCloud3DKeepZ "
               "(voxel/classify/outlier/update); input+output retain height\n";
  setMapParams(nh, /*ground_free=*/true);
  SDFMap2D map3;
  map3.initMap(nh);
  MapROS* mros = map3.diagMapRos();
  if (!mros) {
    std::cerr << "[FAIL] CaseC MapROS null\n";
    ok = false;
  } else {
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>());
    // Dense planar ground near origin (z≈0) for free-ray + planarity.
    addClusterXYZ(cloud, -0.35, 0.0, 0.01, 9, 0.03);
    // Real-height low obstacles at z=5/10/20 cm (must become OCCUPIED, not free).
    const double zs[3] = {0.05, 0.10, 0.20};
    const double xs[3] = {0.70, 0.90, 1.10};
    for (int k = 0; k < 3; ++k) {
      // Cluster large enough to survive radius outlier (r=0.3, min=35).
      addClusterXYZ(cloud, xs[k], 0.0, zs[k], 8, 0.025);
    }
    // Mix: also keep per-point height dump of inputs.
    int n_z05 = 0, n_z10 = 0, n_z20 = 0, n_groundish = 0;
    for (const auto& p : cloud->points) {
      if (std::fabs(p.z - 0.05) < 1e-4) n_z05++;
      else if (std::fabs(p.z - 0.10) < 1e-4) n_z10++;
      else if (std::fabs(p.z - 0.20) < 1e-4) n_z20++;
      else if (p.z >= 0.0 && p.z <= 0.03) n_groundish++;
    }
    std::cout << "[CaseC] input keep-Z counts groundish=" << n_groundish << " z05=" << n_z05
              << " z10=" << n_z10 << " z20=" << n_z20 << " total=" << cloud->points.size()
              << "\n";

    const Quaterniond cam_q = Quaterniond::Identity();
    MapROS::DiagCloud3DStats st =
        mros->diagProcessCloud3DKeepZ(cloud, cam, cam_q);
    std::cout << "[CaseC] filter stats in=" << st.n_in << " down=" << st.n_down
              << " obst_band=" << st.n_obstacle_band << " low_obst=" << st.n_low_obstacle
              << " ground_cands=" << st.n_ground_cands << " planar_rej=" << st.n_planar_reject
              << " obst_after=" << st.n_obstacle_after_outlier
              << " ground_after=" << st.n_ground_after_outlier
              << " xy_obst=" << st.n_filtered_xy << " xy_ground=" << st.n_ground_free_xy << "\n";

    // Expect low obstacles present after outlier and marked OCCUPIED.
    if (st.n_low_obstacle <= 0 || st.n_obstacle_after_outlier <= 0) {
      std::cerr << "[FAIL] CaseC expected low obstacles to survive classify/outlier\n";
      ok = false;
    }
    for (int k = 0; k < 3; ++k) {
      const Vector2d q(xs[k], 0.0);
      const int o = map3.getOccupancy(q);
      if (o != SDFMap2D::OCCUPIED) {
        std::cerr << "[FAIL] CaseC z=" << zs[k] << "m obstacle at (" << q.x() << "," << q.y()
                  << ") occ=" << o << " want OCCUPIED\n";
        ok = false;
      } else {
        std::cout << "[PASS] CaseC z=" << zs[k] << "m → OCCUPIED at (" << q.x() << "," << q.y()
                  << ")\n";
      }
    }
    // Ground free path should have produced some free-ray candidates.
    if (st.n_ground_after_outlier <= 0) {
      std::cerr << "[FAIL] CaseC expected ground free-ray endpoints after outlier\n";
      ok = false;
    } else {
      std::cout << "[PASS] CaseC ground free-ray endpoints after outlier="
                << st.n_ground_after_outlier << "\n";
    }
  }

  std::cout << (ok ? "ALL_PASS\n" : "FAILED\n");
  return ok ? 0 : 1;
}
