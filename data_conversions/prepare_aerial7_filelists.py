#!/usr/bin/python3
'''Prepare Filelists for Aerial7 Segmentation Task.'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import math
import random
import argparse
from datetime import datetime


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', '-f', help='Path to data folder')
    parser.add_argument('--h5_num', '-d', help='Number of h5 files to be loaded each time', type=int, default=10)
    parser.add_argument('--repeat_num', '-r', help='Number of repeatly using each loaded h5 list', type=int, default=2)

    args = parser.parse_args()
    print(args)

    root = args.folder if args.folder else '../../data/aerial7-pcnn'
    splits = ['train', 'test']
    
    split_filelists = dict()
    for split in splits:
        split_filelists[split] = ['./%s/%s\n' % (split, filename) for filename in os.listdir(os.path.join(root, split))
                                  if filename.endswith('.h5')]

    train_h5 = split_filelists['train']

    train_list = os.path.join(root, 'train_files.txt')

    print('{}-Saving {}...'.format(datetime.now(), train_list))

    # write train files
    with open(train_list, 'w') as filelist:
        list_num = math.ceil(len(train_h5) / args.h5_num)
        for list_idx in range(list_num):
            train_list_i = os.path.join(root, 'filelists', 'train_files_g_%d.txt' % list_idx)
            with open(train_list_i, 'w') as filelist_i:
                for h5_idx in range(args.h5_num):
                    filename_idx = list_idx * args.h5_num + h5_idx
                    if filename_idx > len(train_h5) - 1:
                        break
                    filename_h5 = train_h5[filename_idx]
                    print('filename_h5', filename_h5)

                    filelist_i.write('../' + filename_h5)
            for repeat_idx in range(args.repeat_num):
                filelist.write('./filelists/train_files_g_%d.txt\n' % list_idx)
            print('---')

    # write test files
    test_h5 = split_filelists['test']
    test_list = os.path.join(root, 'test_files.txt')
    print('{}-Saving {}...'.format(datetime.now(), test_list))
    with open(test_list, 'w') as filelist:
        list_num = math.ceil(len(test_h5) / args.h5_num)
        for list_idx in range(list_num):
            train_list_i = os.path.join(root, 'filelists', 'test_files_g_%d.txt' % list_idx)
            with open(train_list_i, 'w') as filelist_i:
                for h5_idx in range(args.h5_num):
                    filename_idx = list_idx * args.h5_num + h5_idx
                    if filename_idx > len(test_h5) - 1:
                        break
                    filename_h5 = test_h5[filename_idx]
                    print('filename_h5', filename_h5)

                    filelist_i.write('../' + filename_h5)
            for repeat_idx in range(args.repeat_num):
                filelist.write('./filelists/test_files_g_%d.txt\n' % list_idx)
            print('---')




if __name__ == '__main__':
    main()
