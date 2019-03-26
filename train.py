import data
import numpy as np
import time
import util
import os
import time
import data
import dataloader
import models
import torch
from torch import nn, optim
import statistics
import torch.backends.cudnn as cudnn
import heatmap
from options import Options
import warnings
warnings.filterwarnings("ignore")

#test avg_recall: 0.7932 avg_acc: 0.9583 error: 0.1043
opt = Options().getparse()
localtime = time.asctime(time.localtime(time.time()))
statistics.writelog('\n'+str(localtime)+'\n'+str(opt))

t1 = time.time()
signals,stages = dataloader.loaddataset(opt.dataset_dir,opt.dataset_name,opt.signal_name,opt.signal_num,shuffle=True,BID='median')
stage_cnt_per = statistics.stage(stages)[1]
print('stage_cnt_per:',stage_cnt_per,'\nlength of dataset:',len(stages))
signals_train,stages_train,signals_eval,stages_eval, = data.batch_generator(signals,stages,opt.batchsize,shuffle = True)
print('length of batch:',len(signals_train))
batch_length = len(signals_train)+len(signals_eval)
show_freq = int(len(signals_train)/5)
util.show_menory()
t2 = time.time()
print('load data cost time:',t2-t1)

net=models.CreatNet(opt.model_name)
# print(net)
if not opt.no_cuda:
    net.cuda()
    weight = opt.weight.cuda()
    cudnn.benchmark = True

# print(net)

# time.sleep(2000)
optimizer = torch.optim.Adam(net.parameters(), lr=opt.lr)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=0.95)
criterion = nn.CrossEntropyLoss(weight)
# criterion = nn.CrossEntropyLoss()


def evalnet(net,signals,stages,plot_result={},mode = 'part'):
    net.eval()
    if mode =='part':
        data.shuffledata(signals,stages)
        signals=signals[0:int(len(stages)/2)]
        stages=stages[0:int(len(stages)/2)]

    confusion_mat = np.zeros((5,5), dtype=int)
    for i, (signal, stage) in enumerate(zip(signals,stages), 1):

        signal=data.ToInputShape(signal,opt.model_name,test_flag =True)
        signal,stage = data.ToTensor(signal,stage,no_cuda =opt.no_cuda)
        out = net(signal)
        loss = criterion(out, stage)
        pred = torch.max(out, 1)[1]

        pred=pred.data.cpu().numpy()
        stage=stage.data.cpu().numpy()
        for x in range(len(pred)):
            confusion_mat[stage[x]][pred[x]] += 1
    if mode =='part':
        plot_result['test'].append(statistics.result(confusion_mat)[0])     
    else:
        recall,acc,error  = statistics.result(confusion_mat)
        plot_result['test'].append(recall)   
        heatmap.draw(confusion_mat,name = 'test')
        print('test avg_recall:','%.4f' % recall,'avg_acc:','%.4f' % acc,'error:','%.4f' % error)
    
    statistics.writelog(str(confusion_mat)+'\navg_recall:'+str(recall)+'  avg_acc:'+str(acc)+'  error:'+str(error))
    # torch.cuda.empty_cache()
    return plot_result


plot_result={}
plot_result['train']=[0]
plot_result['test']=[0]
for epoch in range(opt.epochs):
    t1 = time.time()
    statistics.writelog('epoch:'+str(epoch)+'\n')
    confusion_mat = np.zeros((5,5), dtype=int)
    # running_loss, running_recall = 0.0, 0.0
    print('epoch:',epoch+1)
    net.train()
    for i, (signal, stage) in enumerate(zip(signals_train,stages_train), 1):

        signal=data.ToInputShape(signal,opt.model_name,test_flag =False)
        signal,stage = data.ToTensor(signal,stage,no_cuda =opt.no_cuda)

        out = net(signal)
        loss = criterion(out, stage)
        pred = torch.max(out, 1)[1]
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        pred=pred.data.cpu().numpy()
        stage=stage.data.cpu().numpy()
        for x in range(len(pred)):
            confusion_mat[stage[x]][pred[x]] += 1
        if i%show_freq==0:
            # torch.cuda.empty_cache()          
            plot_result['train'].append(statistics.result(confusion_mat)[0])
            heatmap.draw(confusion_mat,name = 'train')
            # plot_result=evalnet(net,signals_eval,stages_eval,plot_result,show_freq,mode = 'part')
            statistics.show(plot_result,epoch+i/(batch_length*0.8))
            confusion_mat[:]=0
            # net.train()

    # torch.cuda.empty_cache() 
    evalnet(net,signals_eval,stages_eval,plot_result,mode = 'all')
    scheduler.step()

    t2=time.time()
    print('cost time: %.2f' % (t2-t1))