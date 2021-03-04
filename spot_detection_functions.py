import numpy as np
import pandas as pd
import tifffile
import trackpy
from skimage.morphology import white_tophat, disk
from skimage.feature import blob_log
import scipy


# functions for detecting and extracting spots from registered images required prior to decoding
def detect_and_extract_spots(imgs_coding, anchors, C, R, imgs_also_without_tophat=None,
                             compute_also_without_tophat=False, norm_anchors=False, use_blob_detector=False,
                             correct_reg_via_trackpy=False, correct_reg_detect_in_all = True,
                             trackpy_diam_detect=5, trackpy_search_range=3, trackpy_prc=64, trackpy_sep=None):
    ###############
    # detects spots using images passed via variable 'anchors' (can be a single (2d) image or R/R+1 2d/3d frames) and
    # extracts detected spots using CxR images passed via 'imgs_coding'
    ###############
    # correct_reg_via_trackpy corrects for imperfect registration by shifting 2d images in cycles >= 1 by a median x-y-offset to anchors[0,:,:]
    ###############
    med_dx=np.empty(anchors.shape[0]).astype(np.int32)
    med_dy=np.empty(anchors.shape[0]).astype(np.int32)
    if use_blob_detector:
        norm_anchors = True
    trackpy.quiet(suppress=True)
    if len(anchors.shape) > 2:  # if there are multiple frames, detect spots in each and link them
        # apply trackpy to each round
        if norm_anchors:
            anchors = (anchors - np.mean(anchors, axis=(-2, -1), keepdims=True)) / np.std(anchors, axis=(-2, -1),
                                                                                        keepdims=True)
        tracks = trackpy.link_df(trackpy.batch(anchors, diameter=trackpy_diam_detect, percentile=trackpy_prc, separation=trackpy_sep),
                                 search_range=trackpy_search_range)
        # find spots appearing in all cycles
        spots_id_all_anchors = tracks['particle'][tracks['frame'] == 0].unique()
        for ind_cy in range(1, anchors.shape[0]):
            spots_id_all_anchors = np.intersect1d(spots_id_all_anchors,
                                                  tracks['particle'][tracks['frame'] == ind_cy].unique())
        num_spots = len(spots_id_all_anchors)
        # print('The number of spots linked across all cycles: {}'.format(num_spots))
        # collect centers of all spots
        centers_y = np.zeros((num_spots, anchors.shape[0]))
        centers_x = np.zeros((num_spots, anchors.shape[0]))
        if len(anchors.shape) > 3: #if there is z dim
            centers_z = np.zeros((num_spots, anchors.shape[0]))
            for i in range(num_spots):
                id_particle = spots_id_all_anchors[i]
                centers_y[i, :] = np.array(tracks[tracks['particle'] == id_particle]['y'])
                centers_x[i, :] = np.array(tracks[tracks['particle'] == id_particle]['x'])
                centers_z[i, :] = np.array(tracks[tracks['particle'] == id_particle]['z'])
        else:
            for i in range(num_spots):
                id_particle = spots_id_all_anchors[i]
                centers_y[i, :] = np.array(tracks[tracks['particle'] == id_particle]['y'])
                centers_x[i, :] = np.array(tracks[tracks['particle'] == id_particle]['x'])
        
        if correct_reg_via_trackpy: #assuming there are only x and y dim; correcting sift wrt anchors[0,:,:]
            for r in range(anchors.shape[0]):
                med_dx[r] = np.around(np.median(centers_x[:,0]-centers_x[:,r])).astype(np.int32)
                med_dy[r] = np.around(np.median(centers_y[:,0]-centers_y[:,r])).astype(np.int32)
            dx_max=np.max(np.abs(med_dx))
            dy_max=np.max(np.abs(med_dy))  
            if (dy_max > 0 or dx_max > 0) and correct_reg_detect_in_all: #anchors should be shifted
                anchors_shifted = np.zeros_like(anchors)
                anchors_expand = np.zeros((anchors.shape[0],anchors.shape[1]+2*dy_max,anchors.shape[2]+2*dx_max))
                anchors_expand[:,dy_max:anchors.shape[1]+dy_max,dx_max:anchors.shape[2]+dx_max] = anchors
                for r in range(anchors.shape[0]):
                    anchors_shifted[r,:,:] = anchors_expand[r,dy_max-med_dy[r]:anchors.shape[1]+dy_max-med_dy[r],dx_max-med_dx[r]:anchors.shape[2]+dx_max-med_dx[r]]
                ##detect and link spots in shifted anchors
                tracks = trackpy.link_df(trackpy.batch(anchors_shifted, diameter=trackpy_diam_detect, percentile=trackpy_prc, separation=trackpy_sep),
                                             search_range=trackpy_search_range)
                # find spots appearing in all cycles
                spots_id_all_anchors = tracks['particle'][tracks['frame'] == 0].unique()
                for ind_cy in range(1, anchors.shape[0]):
                    spots_id_all_anchors = np.intersect1d(spots_id_all_anchors,
                                                              tracks['particle'][tracks['frame'] == ind_cy].unique())
                num_spots = len(spots_id_all_anchors)
                #print('The number of spots linked after correction: {}'.format(num_spots))
                # collect centers of all spots
                centers_y = np.zeros((num_spots, anchors.shape[0]))
                centers_x = np.zeros((num_spots, anchors.shape[0]))
                for i in range(num_spots):
                    id_particle = spots_id_all_anchors[i]
                    centers_y[i, :] = np.array(tracks[tracks['particle'] == id_particle]['y'])
                    centers_x[i, :] = np.array(tracks[tracks['particle'] == id_particle]['x'])
            if not correct_reg_detect_in_all:# collect coordinates setected in anchors[0,:,:]
                #locs = trackpy.locate(anchors[0,:,:], diameter=trackpy_diam_detect, percentile=trackpy_prc)
                #locs_y = np.array(locs['y'])
                #locs_x = np.array(locs['x'])
                locs_y = np.array(tracks['y'][tracks['frame'] == 0])
                locs_x = np.array(tracks['x'][tracks['frame'] == 0])
                num_spots = locs_y.shape[0]
                centers_y = np.repeat(locs_y.reshape((num_spots, 1)), anchors.shape[0], axis=1)
                centers_x = np.repeat(locs_x.reshape((num_spots, 1)), anchors.shape[0], axis=1)

    else:  # otherwise, detect spots using a single frame
        if norm_anchors:
            anchors = (anchors - anchors.mean()) / anchors.std()
        if use_blob_detector:
            locs = blob_log(anchors, min_sigma=trackpy_diam_detect / 2, max_sigma=3 / 2 * trackpy_diam_detect,
                            num_sigma=11, threshold=0.25)
            locs_y = locs[:, 0]
            locs_x = locs[:, 1]
        else:
            locs = trackpy.locate(anchors, diameter=trackpy_diam_detect, percentile=trackpy_prc)
            locs_y = np.array(locs['y'])
            locs_x = np.array(locs['x'])
        num_spots = locs.shape[0]
        centers_y = np.repeat(locs_y.reshape((num_spots, 1)), R, axis=1)
        centers_x = np.repeat(locs_x.reshape((num_spots, 1)), R, axis=1)

    centers_c01 = np.transpose(
        np.stack((centers_x[:, 0], centers_y[:, 0])))  # equivalent to the centers in matlab if + 1

    if (len(anchors.shape) > 2) and (anchors.shape[0]>R):#there are multiple frames and a reference cycle inserted at the beginning, so remove it before extraction
        centers_x = centers_x[:,1:]
        centers_y = centers_y[:,1:]
        med_dx = med_dx[1:]
        med_dy = med_dy[1:]
      
    # extract max intensity values from each (top-hat-ed) coding channel at the center coordinates +- 1 pixel
    if len(imgs_coding.shape)<5:
        if correct_reg_via_trackpy:
            spot_intensities_d = np.zeros((9, num_spots, C, R))
            d = -1
            for dx in np.array([-1, 0, 1]):
                for dy in np.array([-1, 0, 1]):
                    d = d + 1
                    for ind_cy in range(R):
                        x_coord = np.maximum(0, np.minimum(imgs_coding.shape[1] - 1,
                                                           np.around(centers_x[:, ind_cy]).astype('int32') - med_dx[ind_cy] + dx))
                        y_coord = np.maximum(0, np.minimum(imgs_coding.shape[0] - 1,
                                                           np.around(centers_y[:, ind_cy]).astype('int32') - med_dy[ind_cy] + dy))
                        for ind_ch in range(C):
                            spot_intensities_d[d, :, ind_ch, ind_cy] = imgs_coding[y_coord, x_coord, ind_ch, ind_cy]
            spot_intensities = np.max(spot_intensities_d, axis=0)
        else:
            spot_intensities_d = np.zeros((9, num_spots, C, R))
            d = -1
            for dx in np.array([-1, 0, 1]):
                for dy in np.array([-1, 0, 1]):
                    d = d + 1
                    for ind_cy in range(R):
                        x_coord = np.maximum(0, np.minimum(imgs_coding.shape[1] - 1,
                                                           np.around(centers_x[:, ind_cy]).astype('int32') + dx))
                        y_coord = np.maximum(0, np.minimum(imgs_coding.shape[0] - 1,
                                                           np.around(centers_y[:, ind_cy]).astype('int32') + dy))
                        for ind_ch in range(C):
                            spot_intensities_d[d, :, ind_ch, ind_cy] = imgs_coding[y_coord, x_coord, ind_ch, ind_cy]
            spot_intensities = np.max(spot_intensities_d, axis=0)
    else:#there is z dimension
        spot_intensities_d = np.zeros((9, num_spots, C, R))
        d = -1
        for dx in np.array([-1, 0, 1]):
            for dy in np.array([-1, 0, 1]):
                d = d + 1
                for ind_cy in range(R):
                    x_coord = np.maximum(0, np.minimum(imgs_coding.shape[2] - 1,
                                                       np.around(centers_x[:, ind_cy]).astype('int32') + dx))
                    y_coord = np.maximum(0, np.minimum(imgs_coding.shape[1] - 1,
                                                       np.around(centers_y[:, ind_cy]).astype('int32') + dy))
                    z_coord = np.maximum(0, np.minimum(imgs_coding.shape[0] - 1,
                                                       np.around(centers_z[:, ind_cy]).astype('int32')))
                    for ind_ch in range(C):
                        spot_intensities_d[d, :, ind_ch, ind_cy] = imgs_coding[z_coord, y_coord, x_coord, ind_ch, ind_cy]
        spot_intensities = np.max(spot_intensities_d, axis=0)


    if compute_also_without_tophat:
        spot_intensities_d = np.zeros((9, num_spots, C, R))
        d = -1
        for dx in np.array([-1, 0, 1]):
            for dy in np.array([-1, 0, 1]):
                d = d + 1
                for ind_cy in range(R):
                    x_coord = np.maximum(0, np.minimum(imgs_also_without_tophat.shape[1] - 1,
                                                       np.around(centers_x[:, ind_cy]).astype('int32') + dx))
                    y_coord = np.maximum(0, np.minimum(imgs_also_without_tophat.shape[0] - 1,
                                                       np.around(centers_y[:, ind_cy]).astype('int32') + dy))
                    for ind_ch in range(C):
                        spot_intensities_d[d, :, ind_ch, ind_cy] = imgs_also_without_tophat[
                            y_coord, x_coord, ind_ch, ind_cy]
        spot_intensities_notophat = np.max(spot_intensities_d, axis=0)
    else:
        spot_intensities_notophat = None
    return spot_intensities, centers_c01, spot_intensities_notophat#, med_dx, med_dy#, centers_x, centers_y


def load_tiles_to_extract_spots(tifs_path, channels_info, C, R,
                                tile_names, tiles_info, tiles_to_load,
                                spots_params, ind_cy_move_forward_by=0, anchor_available=True, fake_anchor_prc=95, 
                                fake_anchor_gauss_sigma=None, fake_anchor_from_top_hat=False,
                                use_ref_anchor=False,
                                correct_reg_via_trackpy=False, 
                                correct_reg_detect_in_all=False, #relevant only when correct_reg_via_trackpy=True; if False keeps the spots from the first frame passed to the spot detection function after registration correction, and if True, it links the spots after correction
                                anchors_cy_ind_for_spot_detect=None, #which anchors to pass to spot detection (all by default, should be all when correct_reg_via_trackpy=True)
                                norm_anchors=False, use_blob_detector=False,
                                compute_also_without_tophat=False):
    # anchors_cy_ind_for_spot_detect can be any number in {0,..,R-1} to indicate if a single frame should be used
    # for spot detection, otherwise by default all cycles are considered for spot detection

    spots = np.empty((0, C, R))
    spots_notophat = np.empty((0, C, R))
    spots_loc = pd.DataFrame(columns=['X', 'Y', 'Tile'])
    if not ('trackpy_prc' in spots_params):
        spots_params['trackpy_prc'] = 64
    if anchors_cy_ind_for_spot_detect is None:
        if use_ref_anchor:
            anchors_cy_ind_for_spot_detect = np.arange(R+1)
        else:
            anchors_cy_ind_for_spot_detect = np.arange(R)
    print('Extracting spots from: ', end='')
    for y_ind in range(tiles_to_load['y_start'], tiles_to_load['y_end'] + 1):
        for x_ind in range(tiles_to_load['x_start'], tiles_to_load['x_end'] + 1):
            tile_name = 'X' + str(x_ind) + '_Y' + str(y_ind)
            if np.isin(tile_name, tile_names['selected_tile_names']):
                # load selected tile
                print(tile_name, end=' ')
                if x_ind == tiles_info['x_max']:
                    tile_size_x = tiles_info['x_max_size']
                else:
                    tile_size_x = tiles_info['tile_size']
                if y_ind == tiles_info['y_max']:
                    tile_size_y = tiles_info['y_max_size']
                else:
                    tile_size_y = tiles_info['tile_size']

                imgs = np.zeros((tile_size_y, tile_size_x, len(channels_info['channel_names']), R))
                for ind_cy in range(R):
                    for ind_ch in range(len(channels_info['channel_names'])):
                        if channels_info['channel_names'][ind_ch] != 'DAPI':  # no need for dapi
                            try:
                                imgs[:, :, ind_ch, ind_cy] = tifffile.imread(
                                    tifs_path + tiles_info['filename_prefix'] + channels_info['channel_names'][
                                        ind_ch] + '_c0' + str(
                                        ind_cy + 1 + ind_cy_move_forward_by) + '_' + tile_name + '.tif').astype(
                                    np.float32)
                            except:
                                imgs[:, :, ind_ch, ind_cy] = tifffile.imread(
                                    tifs_path + tiles_info['filename_prefix'] + tile_name + '_c0' + str(
                                        ind_cy + 1 + ind_cy_move_forward_by) + '_' + channels_info['channel_names'][
                                        ind_ch] + '.tif').astype(
                                    np.float32)
                                
                if use_ref_anchor:
                    ref_anchor_name = channels_info['channel_names'][4] + '_c0' + str(-1 + 1 + 1) 
                    ref = tifffile.imread(tifs_path + tiles_info['filename_prefix'] + ref_anchor_name + '_' + tile_name + '.tif').astype(np.float32)

                imgs_coding = imgs[:, :, np.where(np.array(channels_info['coding_chs']) == True)[0], :]
                # apply top-hat filtering to each coding channel
                imgs_coding_tophat = np.zeros_like(imgs_coding)
                for ind_cy in range(R):
                    for ind_ch in range(C):
                        imgs_coding_tophat[:, :, ind_ch, ind_cy] = white_tophat(imgs_coding[:, :, ind_ch, ind_cy],
                                                                                disk(spots_params['spot_diam_tophat']))

                # extract anchor channel across all cycles
                if anchor_available:
                    anchors = np.swapaxes(
                        np.swapaxes(
                            np.squeeze(
                                imgs[:, :, np.where(np.array(channels_info['channel_base']) == 'anchor')[0][0], :]),
                            0, 2), 1, 2)
                else:
                    # if anchor is not available, form "fake-anchors" from coding channels (already top-hat filtered + normalized)
                    if fake_anchor_from_top_hat:
                        imgs_for_fake_anchor = imgs_coding_tophat
                    else:
                        imgs_for_fake_anchor = imgs_coding    
                    imgs_for_fake_anchor_norm = (imgs_for_fake_anchor - np.min(imgs_for_fake_anchor, axis=(0, 1),
                                                                           keepdims=True)) / (
                                                      np.percentile(imgs_for_fake_anchor, fake_anchor_prc, axis=(0, 1),
                                                                    keepdims=True) - np.min(imgs_for_fake_anchor,
                                                                                            axis=(0, 1),
                                                                                            keepdims=True))
                    # imgs_coding_tophat_norm = imgs_coding_tophat # without normalization
                    anchors = np.swapaxes(np.swapaxes(imgs_for_fake_anchor_norm.max(axis=2), 0, 2), 1, 2)
                    if not fake_anchor_gauss_sigma is None:
                        #anchors = scipy.ndimage.gaussian_filter(anchors, fake_anchor_gauss_sigma.mean())
                        for r in range(R):
                            anchors[r,:,:] = scipy.ndimage.gaussian_filter(anchors[r,:,:], fake_anchor_gauss_sigma[r])
                            
                    if use_ref_anchor:#insert anchor from the reference round at the beginning
                        #normalize ref anchor with the same per as when creating fake anchors
                        ref_norm = (ref - np.min(ref)) / (np.percentile(ref, fake_anchor_prc) - np.min(ref))
                        anchors = np.concatenate((np.expand_dims(ref_norm, 0), anchors), axis=0)

                anchors = anchors[anchors_cy_ind_for_spot_detect, :,
                          :]  # select only those cycles given in anchors_cy_ind_for_spot_detect

                # detect and extract spots from the loaded tile
                spots_i, centers_i, spots_notophat_i = detect_and_extract_spots(imgs_coding_tophat, anchors, C, R,
                                                                                imgs_coding,
                                                                                compute_also_without_tophat,
                                                                                norm_anchors,
                                                                                use_blob_detector,
                                                                                correct_reg_via_trackpy,
                                                                                correct_reg_detect_in_all,
                                                                                spots_params['trackpy_diam_detect'],
                                                                                spots_params['trackpy_search_range'],
                                                                                spots_params['trackpy_prc'])
                N_i = spots_i.shape[0]
                if N_i > 0:
                    spots = np.concatenate((spots, spots_i))
                    if compute_also_without_tophat:
                        spots_notophat = np.concatenate((spots_notophat, spots_notophat_i))
                    # saving spots locations from the 1st cycle in a data frame (needed for ploting)
                    X = (x_ind - tiles_to_load['x_start']) * tiles_info['tile_size'] + centers_i[:, 0]
                    Y = (y_ind - tiles_to_load['y_start']) * tiles_info['tile_size'] + centers_i[:, 1]
                    Tile = np.tile(np.array([tile_name]), N_i)
                    spots_loc_i = pd.DataFrame(
                        np.concatenate((X.reshape((N_i, 1)), Y.reshape((N_i, 1)), Tile.reshape((N_i, 1))), axis=1),
                        columns=['X', 'Y', 'Tile'], index=None)
                    spots_loc = spots_loc.append(spots_loc_i, ignore_index=True)
    return spots, spots_loc, spots_notophat#, imgs_coding_tophat


def load_tiles(tifs_path, channels_info, C, R, tile_names, tiles_info, tiles_to_load,
               top_hat_coding=True, diam_tophat=3, ind_cy_move_forward_by=0):
    B = (tiles_to_load['y_end'] - tiles_to_load['y_start'] + 1) * (
            tiles_to_load['x_end'] - tiles_to_load['x_start'] + 1)
    b = -1
    tiles = np.zeros((B, tiles_info['tile_size'], tiles_info['tile_size'], len(channels_info['channel_names']), R))
    print('Loading: ', end='')
    for y_ind in range(tiles_to_load['y_start'], tiles_to_load['y_end'] + 1):
        for x_ind in range(tiles_to_load['x_start'], tiles_to_load['x_end'] + 1):
            b = b + 1
            tile_name = 'X' + str(x_ind) + '_Y' + str(y_ind)
            if np.isin(tile_name, tile_names['selected_tile_names']):
                # load selected tile
                print(tile_name, end=' ')
                if x_ind == tiles_info['x_max']:
                    tile_size_x = tiles_info['x_max_size']
                else:
                    tile_size_x = tiles_info['tile_size']
                if y_ind == tiles_info['y_max']:
                    tile_size_y = tiles_info['y_max_size']
                else:
                    tile_size_y = tiles_info['tile_size']

                imgs = np.zeros((tile_size_y, tile_size_x, len(channels_info['channel_names']), R))
                for ind_cy in range(R):
                    for ind_ch in range(len(channels_info['channel_names'])):
                        if channels_info['channel_names'][ind_ch] != 'DAPI':  # no need for dapi
                            try:
                                imgs[:, :, ind_ch, ind_cy] = tifffile.imread(
                                    tifs_path + tiles_info['filename_prefix'] + channels_info['channel_names'][
                                        ind_ch] + '_c0' + str(
                                        ind_cy + 1 + ind_cy_move_forward_by) + '_' + tile_name + '.tif').astype(
                                    np.float32)
                            except:
                                imgs[:, :, ind_ch, ind_cy] = tifffile.imread(
                                    tifs_path + tiles_info['filename_prefix'] + tile_name + '_c0' + str(
                                        ind_cy + 1 + ind_cy_move_forward_by) + '_' + channels_info['channel_names'][
                                        ind_ch] + '.tif').astype(
                                    np.float32)

                if top_hat_coding:
                    imgs_coding = imgs[:, :, np.where(np.array(channels_info['coding_chs']) == True)[0], :]
                    # apply top-hat filtering to each coding channel
                    imgs_coding_tophat = np.zeros_like(imgs_coding)
                    for ind_cy in range(R):
                        for ind_ch in range(C):
                            imgs_coding_tophat[:, :, ind_ch, ind_cy] = white_tophat(imgs_coding[:, :, ind_ch, ind_cy],
                                                                                    disk(diam_tophat))

                    imgs[:, :, np.where(np.array(channels_info['coding_chs']) == True)[0], :] = imgs_coding_tophat

                tiles[b, 0:tile_size_y, 0:tile_size_x, :, :] = imgs

    return tiles


def load_channel_as_fov(tifs_path, channel_name, cycle_name, tile_names, tiles_info, tiles_to_load):
       
    for y_ind in range(tiles_to_load['y_start'], tiles_to_load['y_end'] + 1):
        
        #load the first tile in the given y coordinate
        tile_name = 'X' + str(tiles_to_load['x_start']) + '_Y' + str(y_ind)
        if tiles_to_load['x_start'] == tiles_info['x_max']:
            tile_size_x = tiles_info['x_max_size']
        else:
            tile_size_x = tiles_info['tile_size']
        if y_ind == tiles_info['y_max']:
            tile_size_y = tiles_info['y_max_size']
        else:
            tile_size_y = tiles_info['tile_size']
        if np.isin(tile_name, tile_names['selected_tile_names']):
            try:
                img_y = tifffile.imread(
                    tifs_path + tiles_info['filename_prefix'] + channel_name + '_' + cycle_name + '_' + tile_name + '.tif').astype(
                    np.float32)
            except:
                img_y = tifffile.imread(
                    tifs_path + tiles_info['filename_prefix'] + tile_name + '_' + cycle_name + '_' + channel_name + '.tif').astype(
                    np.float32)                       
        else:
            img_y = np.zeros((tile_size_y, tile_size_x))
            
        # load subsequent tiles in the y coordinate       
        for x_ind in range(tiles_to_load['x_start']+1, tiles_to_load['x_end'] + 1):
            tile_name = 'X' + str(x_ind) + '_Y' + str(y_ind)
            if x_ind == tiles_info['x_max']:
                tile_size_x = tiles_info['x_max_size']
            else:
                tile_size_x = tiles_info['tile_size']
            if y_ind == tiles_info['y_max']:
                tile_size_y = tiles_info['y_max_size']
            else:
                tile_size_y = tiles_info['tile_size']

            if np.isin(tile_name, tile_names['selected_tile_names']):
                try:
                    I = tifffile.imread(
                        tifs_path + tiles_info['filename_prefix'] + channel_name + '_' + cycle_name + '_' + tile_name + '.tif').astype(
                        np.float32)
                except:
                    I = tifffile.imread(
                        tifs_path + tiles_info['filename_prefix'] + tile_name + '_' + cycle_name + '_' + channel_name + '.tif').astype(
                        np.float32)                       
            else:
                I = np.zeros((tile_size_y, tile_size_x))
                
            img_y = np.concatenate((img_y,I), axis=1)
            
        if y_ind > tiles_to_load['y_start']:
            img = np.concatenate((img,img_y), axis=0)
        else:
            img = img_y

    return img