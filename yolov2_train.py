# -*- coding: utf-8 -*-
"""
    yolov2_tensorflow.yolov2_train
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Created on 2016-12-26 17:55
    @author : huangguoxiong
    copyright: (c) 2016 by huangguoxiong.
    license: Apache license, see LICENSE for more details.
"""

import tensorflow as tf
import config.yolov2_config as cfg
import utils.pascal_voc as voc
import utils.stat as stat
import nets.yolov2 as yolo
from utils.timer import Timer
slim = tf.contrib.slim
voc.set_config(cfg)


# Load the images and labels.
#images, labels = voc.gep_nexp_batch()
#print images.shape[0]
## Create the model.
#scene_predictions, depth_predictions, pose_predictions = CreateMultiTaskModel(images)
#
## Define the loss functions and get the total loss.
#classification_loss = slim.losses.softmax_cross_entropy(scene_predictions, scene_labels)
#sum_of_squares_loss = slim.losses.sum_of_squares(depth_predictions, depth_labels)
#pose_loss = MyCustomLossFunction(pose_predictions, pose_labels)
#slim.losses.add_loss(pose_loss) # Letting TF-Slim know about the additional loss.
#
## The following two ways to compute the total loss are equivalent:
#regularization_loss = tf.add_n(slim.losses.gep_regularization_losses())
#total_loss1 = classification_loss + sum_of_squares_loss + pose_loss + regularization_loss
#
## (Regularization Loss is included in the total loss by default).
#total_loss2 = losses.gep_total_loss()
def box_iou(pred,truth):
    p_x = pred[...,0:1]
    p_y = pred[...,1:2]
    p_w = pred[...,2:3]
    p_h = pred[...,3:4]

    p_l = p_x - p_w/2
    p_r = p_x + p_w/2
    p_t = p_y - p_h/2
    p_b = p_y + p_h/2

    t_x = truth[...,0:1]
    t_y = truth[...,1:2]
    t_w = truth[...,2:3]
    t_h = truth[...,3:4]

    t_l = t_x - t_w/2
    t_r = t_x + t_w/2
    t_t = t_y - t_h/2
    t_b = t_y + t_h/2
    # box intersection
    x_w = tf.minimum(t_r , p_r) - tf.maximum(t_l , p_l)
    x_h = tf.minimum(t_b , p_b) - tf.maximum(t_t , p_t)
    area_intersction = x_w * x_h
    area_intersction = tf.maximum(area_intersction,0)
    
    # box union
    area_p = p_w * p_h
    area_t = t_w * t_h
    area_union = area_p + area_t - area_intersction
    return area_intersction/area_union

def box_iou_by_truths(preds,truths,b,i,j,t):
    preds00 = preds[b,j,i,:,:]
    truths00 = truths[b,t,:]
    #print preds00,truths00
    # coords
    p_x = preds00[...,0]
    p_y = preds00[...,1]
    p_w = preds00[...,2]
    p_h = preds00[...,3]

    p_l = p_x - p_w/2
    p_r = p_x + p_w/2
    p_t = p_y - p_h/2
    p_b = p_y + p_h/2

    t_x = truths00[...,0:1]
    t_y = truths00[...,1:2]
    t_w = truths00[...,2:3]
    t_h = truths00[...,3:4]

    t_l = t_x - t_w/2
    t_r = t_x + t_w/2
    t_t = t_y - t_h/2
    t_b = t_y + t_h/2
    # box intersection
    x_w = tf.minimum(t_r , p_r) - tf.maximum(t_l , p_l)
    x_h = tf.minimum(t_b , p_b) - tf.maximum(t_t , p_t)
    area_intersction = x_w * x_h
    area_intersction = tf.maximum(area_intersction,0)
    
    # box union
    area_p = p_w * p_h
    area_t = t_w * t_h
    area_union = area_p + area_t - area_intersction
    return area_intersction/area_union

def box_iou_by_pred(preds,truths):
    truths = tf.expand_dims(truths,1)
    truths = tf.expand_dims(truths,1)
    truths = tf.expand_dims(truths,1)
    # coords
    p_x = preds[...,0:1]
    p_y = preds[...,1:2]
    p_w = preds[...,2:3]
    p_h = preds[...,3:4]

    p_l = p_x - p_w/2
    p_r = p_x + p_w/2
    p_t = p_y - p_h/2
    p_b = p_y + p_h/2

    t_x = truths[...,0]
    t_y = truths[...,1]
    t_w = truths[...,2]
    t_h = truths[...,3]

    t_l = t_x - t_w/2
    t_r = t_x + t_w/2
    t_t = t_y - t_h/2
    t_b = t_y + t_h/2

    # box intersection
    x_w = tf.minimum(t_r , p_r) - tf.maximum(t_l , p_l)
    x_h = tf.minimum(t_b , p_b) - tf.maximum(t_t , p_t)
    area_intersction = x_w * x_h
    area_intersction = tf.maximum(area_intersction,0)
    
    # box union
    area_p = p_w * p_h
    area_t = t_w * t_h
    area_union = area_p + area_t - area_intersction
    return area_intersction/area_union

def tf_post_process(predicts):
    # 1. x,y,w,h处理
    # 2. scale处理
    # 3. class处理
    p_coords = predicts[...,:5]
    p_classes = predicts[...,5:]
    p_x = predicts[...,0:1]
    p_y = predicts[...,1:2]
    p_w = predicts[...,2]
    p_h = predicts[...,3]
    p_c = predicts[...,4:5] #scale
    
    p_index = tf.where(p_x>-99999)
    p_row = tf.reshape(tf.to_float(p_index[:,1:2]),p_x.get_shape())
    p_col = tf.reshape(tf.to_float(p_index[:,2:3]),p_x.get_shape())
    #p_b = tf.reshape(p_index[:,3:4],p_x.get_shape())

    p_x = (p_col + tf.sigmoid(p_x)) /cfg.cell_size
    p_y = (p_row + tf.sigmoid(p_y)) /cfg.cell_size
    
    p_c = tf.sigmoid(p_c)
    #print tf.tile(cfg.anchors[::2],[13*13]) 
    p_w = tf.exp(p_w) * cfg.anchors[::2]/ cfg.cell_size
    p_h = tf.exp(p_h) * cfg.anchors[1::2]/ cfg.cell_size
    p_w = tf.expand_dims(p_w,-1)
    p_h = tf.expand_dims(p_h,-1)

    p_cls_max = tf.reduce_max(p_classes,-1,True)
    p_classes = p_classes - p_cls_max
    p_classes = tf.nn.softmax(p_classes)

    #p_probs = p_classes * p_c
    return tf.concat(4,[p_x,p_y,p_w,p_h,p_c,p_classes])

def sigmoid_gradient(x):
    return (1-x)*x

def delta_obj_scales(pred_scales,cfg_scale,iou):
    d_scales = cfg_scale * ((iou - pred_scales) * sigmoid_gradient(pred_scales))
    return d_scales

def delta_noobj_scales(pred_scales,cfg_scale):
    d_scales = cfg_scale * ((0 - pred_scales) * sigmoid_gradient(pred_scales))
    return d_scales


def do_assign(ref,v,value):
    return tf.assign(ref,v.assign(value))

def _delta_region_box(truths,net,preds,cfg_anchors,cfg_scale,b,i,j,n,t,delta):
    n = tf.to_int32(n)
    n1 = 2 * n
    n2 = 2 * n +1
    pred = preds[b,j,i,n,:4]
    pre = net[b,j,i,n,:4]
    truth = truths[b,n,:4]
    iou = box_iou(pred,truth)
    stat.avg_iou = stat.avg_iou + iou
    t_x = truth[0] * cfg.cell_size - tf.to_float(i)
    t_y = truth[1] * cfg.cell_size - tf.to_float(j)
    t_w = tf.log(truth[2] * cfg.cell_size )#/ cfg.anchors[n1])
    t_h = tf.log(truth[3] * cfg.cell_size )#/ cfg.anchors[n2])
    #print delta
    d1 = do_assign(delta,delta[b,j,i,n,0],cfg.object_scale*(t_x-tf.sigmoid(pre[0])) * sigmoid_gradient(tf.sigmoid(pre[0])))
    d2 = do_assign(d1,delta[b,j,i,n,1],cfg.object_scale*(t_y-tf.sigmoid(pre[1])) * sigmoid_gradient(tf.sigmoid(pre[1])))
    d3 = do_assign(d2,delta[b,j,i,n,2],cfg.object_scale*(t_w-pre[2]))
    d4 = do_assign(d3,delta[b,j,i,n,3],cfg.object_scale*(t_h-pre[3]))
    return d4

def _delta_by_truths(truths,net,preds,delta):
    t_x = truths[...,0:1]
    t_y = truths[...,1:2]
    t_x = t_x * cfg.cell_size
    t_y = t_y * cfg.cell_size

    t_shift_x = t_x * 0
    t_shift_y = t_y * 0

    truths_shift = tf.concat(2,[t_shift_x,t_shift_y,truths[...,2:4]])

    p_x = preds[...,0:1]
    p_y = preds[...,1:2]
    p_shift_x = p_x * 0
    p_shift_y = p_y * 0
    #print preds[:,1,1,:,:]
    #print truths

    preds_shift = tf.concat(4,[p_shift_x,p_shift_y,preds[...,2:4]])

    # 8. compute shift_iou and best_shift_iou_by_pred
    #shift_iou = box_iou_by_pred(preds_shift,truths_shift)
    #print shift_iou
    #best_shift_iou_by_pred = tf.reduce_max(shift_iou,-1,keep_dims=True)
    #print best_shift_iou_by_pred
    
    #print t_x
    for b in xrange(truths.get_shape()[0]):
        for t in xrange(30):
            i = t_x[b,t,0]
            j = t_y[b,t,0]
            i =tf.to_int32(i)
            j =tf.to_int32(j)
            shift_iou = box_iou_by_truths(preds_shift,truths_shift,b,i,j,t)
            best_shift_iou = tf.reduce_max(shift_iou,-1,keep_dims=True)
            #print shift_iou
            best_shift_n = tf.arg_max(shift_iou,0)
            best_shift_n =tf.to_int32(best_shift_n)
        
            #print best_shift_n
            delta_box = _delta_region_box(truths,net,preds,cfg.anchors,cfg.coord_scale,b,i,j,best_shift_n,t,delta)
            print delta_box




def loss(net,labels):
    net_out = tf_post_process(net)
    delta = tf.Variable(tf.zeros(net_out.get_shape()))

    # 1. init delta
    delta_scales = delta[...,4:5]
    delta_region_box = delta[...,:4]

    stat.set_zero()
    # 2. compute delta_scales
    delta_scales = delta_noobj_scales(net_out[...,4:5],cfg.noobject_scale)
    

    # 3. compute avg_anyobj
    stat.avg_anyobj = tf.reduce_sum(net_out[...,4:5])
    # 4. compute best_iou
    iou_by_pred = box_iou_by_pred(net_out,labels)
    best_iou_by_pred = tf.reduce_max(iou_by_pred,-1,keep_dims=True)
    # 5. in delta_scales, select best_iou>threshold to set 0
    cond = best_iou_by_pred > cfg.threshold
    delta_scales = tf.where(cond,delta_scales*0,delta_scales)
    
    # 6. compose of truths_shift
    truths = labels[...,:4]



    # 7. compose of preds_shift
    preds = net_out[...,:4]
    #print preds



    # 9. compute delta_region_box
    _ = _delta_by_truths(truths,net[...,:4],preds,delta)
    
    #print delta
    return delta


def _train(images,labels):
    return loss(images,labels)

def train():
    log_dir = cfg.train_log_path

    images,labels = voc.get_next_batch()
    train_imgs = tf.placeholder(dtype=tf.float32,shape=images.shape)
    train_lbls = tf.placeholder(dtype=tf.float32,shape=labels.shape)
    net = yolo.yolo_net(train_imgs,images.shape[0],trainable=True)
    t_loss = loss(net,train_lbls)
    train_op = tf.train.MomentumOptimizer(cfg.learning_rate,cfg.momentum).minimize(t_loss)

    init = tf.global_variables_initializer()
    sess = tf.Session()
    writer = tf.summary.FileWriter("logs/",sess.graph)
    sess.run(init)
    avg_iou = 0

    for i in xrange(cfg.max_steps):
        with sess.as_default():
            if i % 10 == 0:
                print avg_iou
                print('step:%s,avg_iou:%s' % (i,avg_iou))
            else:
                _,avg_iou = sess.run([train_op,stat.avg_iou], feed_dict={train_imgs: images, train_lbls: labels})

        images,labels = voc.get_next_batch()

    train_writer.add_summary(i)
    sess.close()

train()


    