// ################################
// VLN adapt: THC compatibility shim for PyTorch 2.x (THC/THC.h removed)
// ################################
#pragma once

#include <ATen/ATen.h>
#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAGuard.h>
#include <ATen/cuda/CUDAApplyUtils.cuh>
#include <THC/THCAtomics.cuh>
#include <THC/THCDeviceUtils.cuh>

#include <cuda_runtime.h>
#include <algorithm>
#include <cstdint>

// Explicit ceil-div (THCDeviceUtils may not expose THCCeilDiv to nvcc here)
#ifndef THCCeilDiv
template <typename T>
__host__ __device__ static inline T THCCeilDiv(T a, T b) {
  return (a + b - 1) / b;
}
#endif

#ifndef AT_CUDA_CHECK
#define AT_CUDA_CHECK(EXPR)                                               \
  do {                                                                    \
    cudaError_t __err = EXPR;                                             \
    if (__err != cudaSuccess) {                                           \
      AT_ERROR("CUDA error: ", cudaGetErrorString(__err));                \
    }                                                                     \
  } while (0)
#endif

#ifndef THCudaCheck
#define THCudaCheck(err) AT_CUDA_CHECK(err)
#endif

// Dummy THCState pointer for legacy THCudaMalloc/Free call sites
struct THCState {};

inline void* THCudaMalloc(void* /*state*/, size_t size) {
  void* ptr = nullptr;
  AT_CUDA_CHECK(cudaMalloc(&ptr, size));
  return ptr;
}

inline void THCudaFree(void* /*state*/, void* ptr) {
  if (ptr) {
    AT_CUDA_CHECK(cudaFree(ptr));
  }
}
// ################################
