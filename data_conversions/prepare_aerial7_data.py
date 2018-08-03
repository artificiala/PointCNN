#!/usr/bin/python3
'''Prepare Data for Aerial7 Segmentation Task.'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from multiprocessing import Pool
from multiprocessing import Process

import os
import sys
import math
import h5py
import argparse
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import data_utils

def main():
    parser = argparse.ArgumentParser()
    # parser.add_argument('--filename', '-ff', help='Path to file')

    parser.add_argument('--folder', '-f', help='Path to data folder', default='../../data/aerial7/data')
    parser.add_argument('--max_point_num', '-m', help='Max point number of each sample', type=int, default=8192)
    parser.add_argument('--block_size', '-b', help='Block size', type=float, default=5.0)
    parser.add_argument('--grid_size', '-g', help='Grid size', type=float, default=0.1)
    args = parser.parse_args()
    print(args)
    
    root = args.folder if args.folder else '../../data/aerial7/data'

   


    processes = []
    list_of_files = []
    folders = [os.path.join(root, folder) for folder in ['train', 'test']]
    for folder in folders:
        datasets = [filename[:-4] for filename in os.listdir(folder) if filename.endswith('.npy')]
        for dataset_idx, dataset in enumerate(datasets):
            filename_npy = os.path.join(folder, dataset + '.npy')
            # list_of_files.append(filename_npy)
            processes.append(Process(target=process_pointcloud, args=(filename_npy, args, folder,dataset, dataset_idx)))
            # break
        # break

    # Important MULTIPROCESS 20 CORE = 20 FILE 3 GB PER FILE 
    # Run processes
    for p in processes:
        p.start()

    # Exit the completed processes
    for p in processes:
        p.join()
   
             
def process_pointcloud(filename_npy, args, folder, dataset,dataset_idx):
    
    max_point_num = args.max_point_num
    
    batch_size = 2048
    data = np.zeros((batch_size, max_point_num, 6)) # x,y,z,r,g,b
    data_num = np.zeros((batch_size), dtype=np.int32)
    label = np.zeros((batch_size), dtype=np.int32)
    label_seg = np.zeros((batch_size, max_point_num), dtype=np.int32)
    indices_split_to_full = np.zeros((batch_size, max_point_num), dtype=np.int32)


    print('module name:', __name__)
    print('parent process:', os.getppid())
    print('process id:', os.getpid())
    print('{}-Loading {}...'.format(datetime.now(), filename_npy))
      # load data
    data_loaded = np.load(filename_npy)
    
    xyz = np.array(data_loaded[:, 0:3], dtype='float32')
    rgb = np.array(data_loaded[:, 3:6], dtype='float32')
    labels = np.array(data_loaded[:, 7], dtype='uint8')

    # normalize rgb
    rgb = rgb / 255 - 0.5

    number_of_points = xyz.shape[0]

    # print(xyzrgb[0]) debug check rgb normalize

    offsets = [('zero', 0.0), ('half', args.block_size / 2)]
    
    for offset_name, offset in offsets:
        idx_h5 = 0
        idx = 0
        
        # compute block id
        print('{}-Computing block id of {} points...'.format(datetime.now(), number_of_points))
        xyz_min = np.amin(xyz, axis=0, keepdims=True) - offset
        xyz_max = np.amax(xyz, axis=0, keepdims=True)
        block_size = (args.block_size, args.block_size, 2 * (xyz_max[0, -1] - xyz_min[0, -1]))
        xyz_blocks = np.floor((xyz - xyz_min) / block_size).astype(np.int)

        # find which point belong to each block
        print('{}-Collecting points belong to each block...'.format(datetime.now()))
        blocks, point_block_indices, block_point_counts = np.unique(xyz_blocks, return_inverse=True,
                                                                    return_counts=True, axis=0)   
        # split into x block
        block_point_indices = np.split(np.argsort(point_block_indices), np.cumsum(block_point_counts[:-1]))
        print('{}-{} is split into {} blocks.'.format(datetime.now(), filename_npy, blocks.shape[0]))

        block_to_block_idx_map = dict()
        for block_idx in range(blocks.shape[0]):
            block = (blocks[block_idx][0], blocks[block_idx][1])
            block_to_block_idx_map[(block[0], block[1])] = block_idx


        # merge small blocks into one of their big neighbors
        block_point_count_threshold = args.max_point_num / 10
        nbr_block_offsets = [(0, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (1, 1), (1, -1), (-1, -1)]
        block_merge_count = 0
        for block_idx in range(blocks.shape[0]):
            if block_point_counts[block_idx] >= block_point_count_threshold:
                continue

            block = (blocks[block_idx][0], blocks[block_idx][1])
            for x, y in nbr_block_offsets:
                nbr_block = (block[0] + x, block[1] + y)
                if nbr_block not in block_to_block_idx_map:
                    continue

                nbr_block_idx = block_to_block_idx_map[nbr_block]
                if block_point_counts[nbr_block_idx] < block_point_count_threshold:
                    continue

                block_point_indices[nbr_block_idx] = np.concatenate(
                    [block_point_indices[nbr_block_idx], block_point_indices[block_idx]], axis=-1)
                block_point_indices[block_idx] = np.array([], dtype=np.int)
                block_merge_count = block_merge_count + 1
                break
        print('{}-{} of {} blocks are merged.'.format(datetime.now(), block_merge_count, blocks.shape[0]))

        idx_last_non_empty_block = 0
        for block_idx in reversed(range(blocks.shape[0])):
            if block_point_indices[block_idx].shape[0] != 0:
                idx_last_non_empty_block = block_idx
                break

        # uniformly sample each block
        for block_idx in range(idx_last_non_empty_block + 1):
            point_indices = block_point_indices[block_idx]
            if point_indices.shape[0] == 0:
                continue
            block_points = xyz[point_indices]
            block_min = np.amin(block_points, axis=0, keepdims=True)
            xyz_grids = np.floor((block_points - block_min) / args.grid_size).astype(np.int)
            grids, point_grid_indices, grid_point_counts = np.unique(xyz_grids, return_inverse=True,
                                                                      return_counts=True, axis=0)
            grid_point_indices = np.split(np.argsort(point_grid_indices), np.cumsum(grid_point_counts[:-1]))
            grid_point_count_avg = int(np.average(grid_point_counts))
            point_indices_repeated = []
            for grid_idx in range(grids.shape[0]):
                point_indices_in_block = grid_point_indices[grid_idx]
                repeat_num = math.ceil(grid_point_count_avg / point_indices_in_block.shape[0])
                if repeat_num > 1:
                    point_indices_in_block = np.repeat(point_indices_in_block, repeat_num)
                    np.random.shuffle(point_indices_in_block)
                    point_indices_in_block = point_indices_in_block[:grid_point_count_avg]
                point_indices_repeated.extend(list(point_indices[point_indices_in_block]))
            block_point_indices[block_idx] = np.array(point_indices_repeated)
            block_point_counts[block_idx] = len(point_indices_repeated)
        
        for block_idx in range(idx_last_non_empty_block + 1):
            point_indices = block_point_indices[block_idx]
            if point_indices.shape[0] == 0:
                continue

            block_point_num = point_indices.shape[0]
            block_split_num = int(math.ceil(block_point_num * 1.0 / args.max_point_num))
            point_num_avg = int(math.ceil(block_point_num * 1.0 / block_split_num))
            point_nums = [point_num_avg] * block_split_num
            point_nums[-1] = block_point_num - (point_num_avg * (block_split_num - 1))
            starts = [0] + list(np.cumsum(point_nums))

            np.random.shuffle(point_indices)
            block_points = xyz[point_indices]
            block_min = np.amin(block_points, axis=0, keepdims=True)
            block_max = np.amax(block_points, axis=0, keepdims=True)
            block_center = (block_min + block_max) / 2
            block_center[0][-1] = block_min[0][-1]
            block_points = block_points - block_center  # align to block bottom center
            x, y, z = np.split(block_points, (1, 2), axis=-1)
            block_xzyrgb = np.concatenate([x, z, y, rgb[point_indices]], axis=-1)
            # print('block_xzyrgb.shape', block_xzyrgb.shape)
            block_labels = labels[point_indices]

            for block_split_idx in range(block_split_num):
                start = starts[block_split_idx]
                point_num = point_nums[block_split_idx]
                end = start + point_num
                idx_in_batch = idx % batch_size
                data[idx_in_batch, 0:point_num, ...] = block_xzyrgb[start:end, :]
                data_num[idx_in_batch] = point_num
                label[idx_in_batch] = dataset_idx  # won't be used...
                label_seg[idx_in_batch, 0:point_num] = block_labels[start:end]
                indices_split_to_full[idx_in_batch, 0:point_num] = point_indices[start:end]
                
                if ((idx + 1) % batch_size == 0) or \
                        (block_idx == idx_last_non_empty_block and block_split_idx == block_split_num - 1):
                    item_num = idx_in_batch + 1
                    filename_h5 = os.path.join(folder, dataset + '_%s_%d.h5' % (offset_name, idx_h5))
                    print('{}-Saving {}...'.format(datetime.now(), filename_h5))

                    file = h5py.File(filename_h5, 'w')
                    file.create_dataset('data', data=data[0:item_num, ...])
                    file.create_dataset('data_num', data=data_num[0:item_num, ...])
                    file.create_dataset('label', data=label[0:item_num, ...])
                    file.create_dataset('label_seg', data=label_seg[0:item_num, ...])
                    file.create_dataset('indices_split_to_full', data=indices_split_to_full[0:item_num, ...])
                    file.close()

                    
                    idx_h5 = idx_h5 + 1
                idx = idx + 1
if __name__ == '__main__':
    main()
    print('{}-Done.'.format(datetime.now()))
