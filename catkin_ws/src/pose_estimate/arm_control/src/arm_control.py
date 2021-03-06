#!/usr/bin/env python

import roslib
import rospy
from text_msgs.srv import *
from text_msgs.msg import *
from arm_operation.srv import *
from arm_operation.msg import *
from std_srvs.srv import Trigger, TriggerResponse,TriggerRequest, Empty, EmptyResponse, EmptyRequest

from pyquaternion import Quaternion 
from converter import rpy_to_rot, rot_to_rpy
from scipy.spatial.transform import Rotation as R

Joint_Server = "/ur5_control_server/ur_control/goto_joint_pose"
Pose_Server = "/ur5_control_server/ur_control/goto_pose"
Straight_Server = "/ur5_control_server/ur_control/go_straight"

## Cam on Hand
# Home = [5.967301845550537, -1.7598593870746058, 1.4289522171020508, -1.2384098211871546, -1.4981196562396448, -0.08584672609438115]

## Vacuum Srv
Suck_srv = "/vacuum_control/suck"
Normal_srv = "/vacuum_control/normal"
Release_srv = "/vacuum_control/weak_blow"
Gripper_state = "/vacuum_control/off"
Vacuum_state = "/vacuum_control/on"

## Static Cam
# Home = [4.835045337677002, -1.5105884710894983, 1.8466014862060547, -1.875340763722555, -1.5207436720477503, 0.012231024913489819]
Home = [5.075979709625244, -1.776654068623678, 2.087050437927246, -1.8620675245868128, -1.5144646803485315, 0.25272220373153687]
Flip_down = [6.266934871673584, -1.1545036474811, 2.034102439880371, -0.7331102530108851, 3.107348918914795, 1.7475026845932007]
Flip_up = [6.266911029815674, -1.3783600966082972, 1.8973026275634766, -0.3725341002093714, 3.107229471206665, 1.7475026845932007]

Throw_up = [6.266191005706787, -1.4788311163531702, 2.005006790161133, -0.3949926535235804, 3.109395980834961, 1.7303341627120972]

### Data science project
Raisin_list = [[5.461093425750732, -1.5132268110858362, 1.5177922248840332, -1.5628412405597132, -1.5638211409198206, 0.7159885764122009],\
            [5.447961807250977, -1.1255162397967737, 1.9375662803649902, -3.862631146107809, -2.182455841694967, 0.039460308849811554],\
            [5.106770992279053, -0.8373449484454554, 1.717036247253418, -3.9966724554644983, -1.9069741407977503, 0.030188262462615967],\
            [5.034962177276611, -0.6595209280597132, 1.3412714004516602, -3.799537960683004, -1.8350942770587366, 0.028259553015232086],\
            [5.040513515472412, -0.6778886953936976, 1.3798398971557617, -3.8197696844684046, -1.8407357374774378, 0.028475267812609673]]

Crayon_list = [[5.461093425750732, -1.5132268110858362, 1.5177922248840332, -1.5628412405597132, -1.5638211409198206, 0.7159885764122009],\
            [5.447961807250977, -1.1255162397967737, 1.9375662803649902, -3.862631146107809, -2.182455841694967, 0.039460308849811554],\
            [5.426207542419434, -0.6533506552325647, 1.3531436920166016, -3.847229305897848, -2.2398951689349573, 0.018783774226903915],\
            [5.2929534912109375, -0.41357690492738897, 0.8479938507080078, -3.581275765095846, -2.106464211140768, 0.019646264612674713]]

class arm_control(object):
    def __init__(self):
        self.mani_req = manipulationRequest()

        self.arm_move_srv = rospy.Service("~move_to", manipulation, self.srv_move)
        self.arm_home_srv = rospy.Service("~home", Trigger, self.srv_home)
        self.flip_srv = rospy.Service("~flip", Trigger, self.srv_flip)
        self.toss_srv = rospy.Service("~toss", Trigger, self.srv_toss)
        self.suck_process_srv = rospy.Service("~suck_process", Trigger, self.srv_suck)

        ### Data science 
        self.raisin = rospy.Service("~raisin", Trigger, self.srv_raisin)
        self.raisin = rospy.Service("~crayon", Trigger, self.srv_crayon)


    def srv_move(self, req_mani):

        rospy.wait_for_service('/ur5_control_server/ur_control/goto_pose')
        try:
            ur5_pose_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_pose', target_pose)
            req = target_poseRequest()
            req.target_pose = req_mani.pose
            req.factor = 0.6
            resp1 = ur5_pose_ser(req)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e

    def srv_home(self, req):

        rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
        try:
            ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
            req = joint_poseRequest()
            msg = joint_value()
            for i in range(6):
                msg.joint_value[i] = Home[i]
            req.joints.append(msg)
            req.factor = 0.75
            resp1 = ur5_joint_ser(req)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e

        rospy.loginfo("No object. Finish the task")
        return TriggerResponse(success=True, message="Request accepted.")

    def srv_flip(self, req):
        self.joint_func(Flip_up)
        rospy.sleep(0.1)
        self.joint_func(Flip_down)
        rospy.sleep(0.1)
        self.suck_release()
        self.joint_func(Flip_up)
        return TriggerResponse(success=True, message="Request accepted.")
    
    def srv_toss(self, req):
        self.joint_func(Throw_up)
        rospy.sleep(0.1)
        self.suck_release()
        return TriggerResponse(success=True, message="Request accepted.")

    def srv_suck(self, req):

        self.suck_func()
        return TriggerResponse(success=True, message="Request accepted.")


    def joint_func(self, joint):
        rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
        try:
            ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
            req = joint_poseRequest()
            msg = joint_value()
            for i in range(6):
                msg.joint_value[i] = joint[i]
            req.joints.append(msg)
            req.factor = 0.7
            resp1 = ur5_joint_ser(req)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e

    def suck_release(self):

        rospy.wait_for_service(Release_srv, timeout=10)
        release_obj = rospy.ServiceProxy(Release_srv, Empty)
        req = EmptyRequest()
        release_obj(req)
        rospy.sleep(0.5)
        rospy.wait_for_service(Gripper_state, timeout=10)
        two_finger_srv = rospy.ServiceProxy(Gripper_state, Empty)
        two_finger_srv(req)
        rospy.sleep(0.3)
        rospy.wait_for_service(Normal_srv, timeout=10)
        normal = rospy.ServiceProxy(Normal_srv, Empty)
        normal(req)
        rospy.sleep(0.3)

    def suck_func(self):
        rospy.wait_for_service(Vacuum_state, timeout=10)
        vacuum_on = rospy.ServiceProxy(Vacuum_state, Empty)
        req = EmptyRequest()
        vacuum_on(req)
        rospy.sleep(0.3)
        rospy.wait_for_service(Suck_srv, timeout=10)
        suck = rospy.ServiceProxy(Suck_srv, Empty)
        suck(req)
        rospy.sleep(0.3)

###################################################3
    def srv_raisin(self, req_mani):

        for joint in Raisin_list:
            rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
            try:
                ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
                req = joint_poseRequest()
                msg = joint_value()
                for i in range(6):
                    msg.joint_value[i] = joint[i]
                req.joints.append(msg)
                req.factor = 0.5
                resp1 = ur5_joint_ser(req)
            except rospy.ServiceException, e:
                print "Service call failed: %s"%e

            rospy.sleep(0.5)

        rospy.sleep(0.5)
        rospy.wait_for_service('/gripper_control/open')
        try:
            gripper_close_ser = rospy.ServiceProxy('/gripper_control/open', Empty)
            req = EmptyRequest()
            resp1 = gripper_close_ser(req)
            rospy.sleep(1)

        except rospy.ServiceException, e:
            print "Service call failed: %s"%e  

        rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
        try:
            ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
            req = joint_poseRequest()
            msg = joint_value()
            for i in range(6):
                msg.joint_value[i] = Raisin_list[2][i]
            req.joints.append(msg)
            req.factor = 0.5
            resp1 = ur5_joint_ser(req)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e    

        return TriggerResponse(success=True, message="Request accepted.")

    def srv_crayon(self, req_mani):

        for joint in Crayon_list:
            rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
            try:
                ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
                req = joint_poseRequest()
                msg = joint_value()
                for i in range(6):
                    msg.joint_value[i] = joint[i]
                req.joints.append(msg)
                req.factor = 0.5
                resp1 = ur5_joint_ser(req)
            except rospy.ServiceException, e:
                print "Service call failed: %s"%e

            rospy.sleep(0.5)

        rospy.sleep(0.5)
        rospy.wait_for_service('/gripper_control/open')
        try:
            gripper_close_ser = rospy.ServiceProxy('/gripper_control/open', Empty)
            req = EmptyRequest()
            resp1 = gripper_close_ser(req)
            rospy.sleep(1)

        except rospy.ServiceException, e:
            print "Service call failed: %s"%e  

        rospy.wait_for_service('/ur5_control_server/ur_control/goto_joint_pose')
        try:
            ur5_joint_ser = rospy.ServiceProxy('/ur5_control_server/ur_control/goto_joint_pose', joint_pose)
            req = joint_poseRequest()
            msg = joint_value()
            for i in range(6):
                msg.joint_value[i] = Crayon_list[2][i]
            req.joints.append(msg)
            req.factor = 0.5
            resp1 = ur5_joint_ser(req)
        except rospy.ServiceException, e:
            print "Service call failed: %s"%e    

        return TriggerResponse(success=True, message="Request accepted.")

######################################################################################################################
    def shutdown_cb(self):
        rospy.loginfo("Node shutdown")


if __name__ == '__main__':
    rospy.init_node('arm_control', anonymous=False)
    node = arm_control()
    rospy.on_shutdown(node.shutdown_cb)
    rospy.spin()

