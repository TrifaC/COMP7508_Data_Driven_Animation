import numpy as np
from scipy.spatial.transform import Rotation as R
from scipy.spatial.transform import Slerp

from file_io import BVHMotion
from Viewer.controller import SimpleViewer
from Viewer.viewer import ShowBVHUpdate

'''
Find the betweening data between left_data and right_data
Parameters:
    - left_data: the left data
    - right_data: the right data
    - t: the number of betweening frames
    - method: the interpolation method, 'linear' or 'slerp'
Return: An array for the betweening data, 
        if return_first_key=True, then including the known left one, 
        for example, if t=9, then the result should be 9 frames including the left one
'''
def interpolation(left_data, right_data, t, method='linear', return_first_key=True):
    res = [left_data] if return_first_key else []
    '''
    TODO: Implement following functions
    Hints:
        1. The shape of data is (num_joints, 3) for position and (num_joints, 4) for rotation
        2. The rotation data is in quaternion format
        3. We use linear interpolation for position and slerp for rotation
            * The linear interpolation can be obtained by the following formula:
                data_between = left_data + (right_data - left_data) * (i / t)
        4. We use scipy.spatial.transform.Slerp to do slerp interpolation (https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Slerp.html)
            * The Slerp can be obtained by the following code:
                key_rots = R.from_quat([q1, q2])
                key_frames= [0, 1]
                slerp = Slerp(key_times, key_rots)
                new_key_frames = np.linspace(0, 1, t+1))
                interp_rots = slerp(new_key_frames)
            * The slerp in scipy doesn't support quaternion with shape (num_joints, 4), 
              so you need to take the quaternion for each joint in a loop with joint_num,
              like left_data[joint_idx], then combine them after the loop.
            * Don't take the last frame of slerp, because it is the same as the right_data
    '''
    ########## Code Start ############
    print("==================== Interpolation: Run. ====================")
    if method == 'linear':
        # iterate each frame between the start and end.
        for frame_index in range(1, t):
            frame_between = left_data + (right_data - left_data) * (frame_index / t)
            res.append(frame_between)
        return res
    elif method == 'slerp':
        # Create a nd array, with t frames, 25 joints and a quaternion.
        tmp_frame_data_set = np.zeros((t-1, 25, 4))
        # Remember to set the left data.
        tmp_frame_data_set[0] = res[0]
        # iterate each joint of the character.
        for joint_index, joint_quaternion in enumerate(left_data):
            key_rotation = R.from_quat([left_data[joint_index], right_data[joint_index]])
            key_frame_timestamps = [0, 1]
            slerp = Slerp(key_frame_timestamps, key_rotation)
            new_key_frames = np.linspace(0, 1, t+1)
            interpolation_rotation = slerp(new_key_frames)
            # after get the interpolation rotation of each frame, we should split the value of each joint.
            for frame_index in range(1, t-1):
                # assign the frame joint value from the joints value of all frame.
                tmp_frame_data_set[frame_index][joint_index] = interpolation_rotation.as_quat()[frame_index]
        for frame_between in tmp_frame_data_set:
            res.append(frame_between)
        return res
    ########## Code End ############

def part1_key_framing(viewer, time_step, target_step):
    motion = BVHMotion('data/motion_walking.bvh')
        
    motio_length = motion.local_joint_positions.shape[0]
    keyframes = np.arange(0, motio_length, time_step)
    
    new_motion_local_positions, new_motion_local_rotations = [], []
    
    previous_frame_idx = 0
    for current_frame_idx in keyframes[1:]:
        between_local_pos = interpolation(motion.local_joint_positions[previous_frame_idx],
                                          motion.local_joint_positions[current_frame_idx], 
                                          target_step - 1, 'linear')
        between_local_rot = interpolation(motion.local_joint_rotations[previous_frame_idx], 
                                          motion.local_joint_rotations[current_frame_idx], 
                                          target_step - 1, 'slerp')
        new_motion_local_positions.append(between_local_pos)
        new_motion_local_rotations.append(between_local_rot)
        previous_frame_idx = current_frame_idx
    
    res_motion = motion.raw_copy()
    res_motion.local_joint_positions = np.concatenate(new_motion_local_positions)
    res_motion.local_joint_rotations = np.concatenate(new_motion_local_rotations)
    
    translation, orientation = res_motion.batch_forward_kinematics()
    task = ShowBVHUpdate(viewer, res_motion.joint_name, translation, orientation)
    viewer.addTask(task.update)
    
'''
Combine two different motions into one motion
Parameters:
    - motion1: the first motion
    - motion2: the second motion
    - last_frame_index: the last frame index of the first motion
    - start_frame_indx: the start frame index of the second motion
    - between_frames: the number of frames between the two motions
    - searching_frames: the number of frames for searching the closest frame
    - method: the interpolation method, 'interpolation' or 'inertialization'
'''
def concatenate_two_motions(motion1, motion2, last_frame_index, start_frame_indx, between_frames, searching_frames=20, method='interpolation'):
    '''
    TODO: Implement following functions
    Hints:
        1. We should operate on the local joint positions and rotations
            motion.local_joint_positions: (num_frames, num_joints, 3)
            motion.local_joint_rotations: (num_frames, num_joints, 4)
        2. There are five steps in the concatenation:
            i) get the searching windows for motion 1 and motion 2 
                win_1 = motion1.local_joint_rotations[last_frame_index - searching_frames:last_frame_index + searching_frames]
                win_2 = motion2.local_joint_rotations[max(0, start_frame_indx - searching_frames):start_frame_indx + searching_frames]
            ii) find the closest frame in motion 1 searching window and motion 2 searching window
                * You can use similarity matrix in DTW (Dynamic Time Warping) to find the closest frame (motion editing slides)
                * sim_matrix is a matrix with shape (win_1.shape[0], win_2.shape[0])
                * sim_matrix[i, j] = np.linalg.norm(search_source[i] - search_target[j])
                * Find the minimum value in sim_matrix and get the corresponding index i and j
            iii) the i and j is the index in the window, so convert it to the index in the motion
            iv) we have the pose in motion_1(real_i) and motion_2(real_j), then we can do the interpolation
                * The interpolation should be done for the *positions* and *rotations* both
                * You must shift the root positions of motion_2(real_j) to the root positions of motion_1(real_i)
            v) combine the motion1, betweening, motion2 into one motion (have been provided)
        3. You can get all marks if you finish above steps correctly, but bonus will be given if you can do any one of them:
            (bonus) There are N between_frames, but the root position in these frames are not considered
            (bonus) The velocity of two motions are not the same, it can give different weight to the two motions interpolation
            (bonus) The inertialization method provides the best results ref:https://theorangeduck.com/page/spring-roll-call#inertialization
            (bonus) Any way to produce more smooth and natural transitions
    
    Useful functions:
        1. The difference between two vectors: np.linalg.norm(a - b)
        2. The index of minimal value in a matrix: np.min(sim_matrix)
        3. local_joint_rotations = motion.local_joint_rotations
        4. local_joint_positions = motion.local_joint_positions
        5. Visualize the sim_matrix matrix:
            import matplotlib.pyplot as plt
            plt.imshow(sim_matrix)
            plt.show() # You can use plt.savefig('sim_matrix.png') to save the image
    '''
    
    ########## Code Start ############
    # search_win1 = 
    # search_win2 = 
    
    # sim_matrix = 
    # min_idx = 
    # i, j = min_idx // sim_matrix.shape[1], min_idx % sim_matrix.shape[1]
    # real_i, real_j = 
    
    # between_local_pos = 
    # between_local_rot = 
    
    ########## Code End ############
    
    res = motion1.raw_copy()
    res.local_joint_positions = np.concatenate([motion1.local_joint_positions[:real_i],
                                                between_local_pos,
                                                motion2.local_joint_positions[real_j:]], 
                                                axis=0)
    res.local_joint_rotations = np.concatenate([motion1.local_joint_rotations[:real_i],
                                                    between_local_rot, 
                                                    motion2.local_joint_rotations[real_j:]], 
                                                    axis=0)
    return res

        
def part2_concatenate(viewer, between_frames, example=False):
    walk_forward = BVHMotion('data/motion_walking.bvh')
    run_forward = BVHMotion('data/motion_running.bvh')
    run_forward.adjust_joint_name(walk_forward.joint_name)
    
    last_frame_index = 40
    start_frame_indx = 0
    
    if not example:
        motion = concatenate_two_motions(walk_forward, run_forward, last_frame_index, start_frame_indx, between_frames, method='interpolation')
    else:
        motion = walk_forward.raw_copy()
        motion.local_joint_positions = np.concatenate([walk_forward.local_joint_positions[:last_frame_index],
                                                       run_forward.local_joint_positions[start_frame_indx:]], 
                                                       axis=0)
        motion.local_joint_rotations = np.concatenate([walk_forward.local_joint_rotations[:last_frame_index],
                                                        run_forward.local_joint_rotations[start_frame_indx:]], 
                                                        axis=0)         
    
    translation, orientation = motion.batch_forward_kinematics()
    task = ShowBVHUpdate(viewer, motion.joint_name, translation, orientation)
    viewer.addTask(task.update)
    pass


def main():
    viewer = SimpleViewer()  

    # part1_key_framing(viewer, 10, 10)
    # part1_key_framing(viewer, 10, 5)
    # part1_key_framing(viewer, 10, 20)
    part1_key_framing(viewer, 10, 30)
    # part2_concatenate(viewer, between_frames=8, example=True)
    # part2_concatenate(viewer, between_frames=8)  
    viewer.run()


if __name__ == '__main__':
    main()
