/**
 * Native MapROS 3D-keep-Z replay from a CSV of world points (x,y,z).
 * Offline diagnostic only — does not touch the live deploy map.
 *
 * Usage:
 *   rosrun plan_env test_map_cloud_csv_replay /path/to/cloud.csv [cam_x cam_y cam_z]
 */
#include <plan_env/sdf_map2d.h>
#include <plan_env/map_ros.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <ros/ros.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using apexnav_planner::MapROS;
using apexnav_planner::SDFMap2D;
using Eigen::Quaterniond;
using Eigen::Vector2d;
using Eigen::Vector3d;

static void setParams(ros::NodeHandle& nh)
{
  nh.setParam("is_real_world", true);
  nh.setParam("sdf_map/resolution", 0.05);
  nh.setParam("sdf_map/map_size_x", 20.0);
  nh.setParam("sdf_map/map_size_y", 20.0);
  nh.setParam("sdf_map/obstacles_inflation", 0.18);
  nh.setParam("sdf_map/local_bound", 5.0);
  nh.setParam("sdf_map/optimistic", false);
  nh.setParam("sdf_map/signed_dist", false);
  nh.setParam("sdf_map/ray_mode", 0);
  nh.setParam("sdf_map/p_hit", 0.70);
  nh.setParam("sdf_map/p_miss", 0.35);
  nh.setParam("sdf_map/p_min", 0.12);
  nh.setParam("sdf_map/p_max", 0.97);
  nh.setParam("sdf_map/p_occ", 0.80);
  nh.setParam("sdf_map/max_ray_length", 5.0);
  nh.setParam("map_ros/ground_free_ray_enable", true);
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

static bool loadCsv(const std::string& path, pcl::PointCloud<pcl::PointXYZ>::Ptr cloud)
{
  std::ifstream ifs(path);
  if (!ifs.is_open())
    return false;
  std::string line;
  std::getline(ifs, line);  // header
  while (std::getline(ifs, line)) {
    if (line.empty())
      continue;
    std::stringstream ss(line);
    std::string a, b, c;
    if (!std::getline(ss, a, ','))
      continue;
    if (!std::getline(ss, b, ','))
      continue;
    if (!std::getline(ss, c, ','))
      continue;
    pcl::PointXYZ p;
    p.x = std::stof(a);
    p.y = std::stof(b);
    p.z = std::stof(c);
    cloud->points.push_back(p);
  }
  return !cloud->empty();
}

int main(int argc, char** argv)
{
  ros::init(argc, argv, "test_map_cloud_csv_replay", ros::init_options::AnonymousName);
  if (argc < 2) {
    std::cerr << "Usage: test_map_cloud_csv_replay cloud.csv [cam_x cam_y cam_z]\n";
    return 2;
  }
  ros::NodeHandle nh("~");
  setParams(nh);
  SDFMap2D map;
  map.initMap(nh);
  MapROS* mros = map.diagMapRos();
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud(new pcl::PointCloud<pcl::PointXYZ>());
  if (!loadCsv(argv[1], cloud)) {
    std::cerr << "[FAIL] cannot load " << argv[1] << "\n";
    return 1;
  }
  Vector3d cam(0, 0, 0.9);
  if (argc >= 5) {
    cam = Vector3d(std::stod(argv[2]), std::stod(argv[3]), std::stod(argv[4]));
  } else if (!cloud->empty()) {
    // fallback: camera above cloud centroid
    Eigen::Vector3d mean(0, 0, 0);
    for (const auto& p : cloud->points) mean += Eigen::Vector3d(p.x, p.y, p.z);
    mean /= static_cast<double>(cloud->points.size());
    cam = Vector3d(mean.x(), mean.y(), mean.z() + 0.9);
  }
  std::cout << "[CSV] n=" << cloud->points.size() << " cam=(" << cam.transpose() << ")\n";
  MapROS::DiagCloud3DStats st =
      mros->diagProcessCloud3DKeepZ(cloud, cam, Quaterniond::Identity());
  std::cout << "[STATS] in=" << st.n_in << " down=" << st.n_down
            << " low_obst=" << st.n_low_obstacle << " ground_cands=" << st.n_ground_cands
            << " planar_rej=" << st.n_planar_reject << " obst_after=" << st.n_obstacle_after_outlier
            << " ground_after=" << st.n_ground_after_outlier << " xy_obst=" << st.n_filtered_xy
            << " xy_ground=" << st.n_ground_free_xy << "\n";

  // Sample a few ground XY cells near mean of low-z points
  int n_free = 0, n_occ = 0, n_unk = 0, n_query = 0;
  for (const auto& p : cloud->points) {
    if (p.z < 0.0f || p.z > 0.03f)
      continue;
    n_query++;
    if (n_query > 40)
      break;
    const int o = map.getOccupancy(Vector2d(p.x, p.y));
    if (o == SDFMap2D::FREE)
      n_free++;
    else if (o == SDFMap2D::OCCUPIED)
      n_occ++;
    else
      n_unk++;
  }
  std::cout << "[OCC_SAMPLE] queried_lowz=" << n_query << " free=" << n_free << " occ=" << n_occ
            << " unk=" << n_unk << "\n";
  const bool ok = st.n_ground_after_outlier > 0 || st.n_obstacle_after_outlier > 0;
  std::cout << (ok ? "CSV_REPLAY_PASS\n" : "CSV_REPLAY_FAIL\n");
  return ok ? 0 : 1;
}
