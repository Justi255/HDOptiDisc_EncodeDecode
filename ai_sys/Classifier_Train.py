import os

import torch
from torch.utils.data import DataLoader
import torch.nn.functional as F
import numpy as np
import sys
import datetime
np.set_printoptions(threshold=sys.maxsize)

from BaseModel import BaseModel
from LR import LR
from XGBoost import XGBoost
from MLP import MLP
from CNN import CNN
from Unet1D import UNet1D
from RNN import RNN
from Transformer import Transformer
sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__))))
from lib.Params import Params
from lib.Classifier_Dataset import PthDataset
sys.path.pop()

def main():
    global params
    params = Params()

    # device
    os.environ['CUDA_VISIBLE_DEVICES'] = "0"
    if torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
        
    # data loader
    train_dataset = PthDataset(file_path='../data/classifier_train_set.pth')
    test_dataset = PthDataset(file_path='../data/classifier_test_set.pth')
    val_dataset = PthDataset(file_path='../data/classifier_validate_set.pth')

    # model
    model_file = None
    is_nn = 0
    if params.model_arch == "lr":
        model = LR(params)
        model_file = "lr_model.joblib"
    elif params.model_arch == "xgboost":
        model = XGBoost(params)
        model_file = "xgb_model.json"
    elif params.model_arch == "mlp":
        is_nn = 1
        model = MLP(params, device).to(device)
        model_file = "mlp.pth.tar"
    elif params.model_arch == "cnn":
        is_nn = 1
        model = CNN(params, device).to(device)
        model_file = "cnn.pth.tar"
    elif params.model_arch == "unet":
        is_nn = 1
        model = UNet1D(params, device).to(device)
        model_file = "unet.pth.tar"
    elif params.model_arch == "rnn":
        is_nn = 1
        model = RNN(params, device).to(device)
        model_file = "rnn.pth.tar"
    elif params.model_arch == "transformer":
        is_nn = 1
        model = Transformer(params, device).to(device)
        model_file = "transformer.pth.tar"
    
    # model dir
    if not os.path.exists(params.model_dir):
        os.makedirs(params.model_dir)
        
    model_path = f"{params.model_dir}/{model_file}"
    
    if not is_nn:
        X_train, y_train = train_dataset.data.numpy().reshape(-1, 6), train_dataset.label.numpy().reshape(-1)
        X_test,  y_test  = test_dataset.data.numpy().reshape(-1, 6),  test_dataset.label.numpy().reshape(-1)
        X_val,   y_val   = val_dataset.data.numpy().reshape(-1, 6),   val_dataset.label.numpy().reshape(-1)
    
        model.fit(X_train, y_train, X_test, y_test)
        
        y_val_pred = model.decode(len(X_val), X_val)
        ber = (np.sum(np.abs(y_val - y_val_pred))/y_val.shape[0])
        print('Validation ber: {}'.format(ber))
        
        model.save_model(model_path)
        
        if params.model_arch == "xgboost":
            model.feature_importance()
    else:
        train_loader = DataLoader(train_dataset, batch_size=params.batch_size_train, shuffle=True, num_workers=4)
        test_loader = DataLoader(test_dataset, batch_size=params.batch_size_test, shuffle=False, num_workers=4)
        val_loader = DataLoader(val_dataset, batch_size=params.batch_size_val, shuffle=False, num_workers=4)
        
        # criterion and optimizer
        optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), 
                                    lr=params.learning_rate, 
                                    eps=1e-08, 
                                    weight_decay=params.weight_decay)
    
        # output dir 
        dir_name = '../output/output_' + datetime.datetime.strftime(datetime.datetime.now(), '%Y_%m_%d_%H_%M_%S') + '/'
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)
        result_path = dir_name + params.result_file
        
        try:
            result = open(result_path, 'w+')
            print(f"File {result_path} opened successfully.")
        except IOError as e:
            print(f"Error opening file {result_path}: {e}")

        # train and validation
        for epoch in range(params.num_epoch):
            
            # train and validate
            train_loss = train(train_loader, model, optimizer, epoch, device)
            test_loss, ber = validate(test_loader, val_loader, model, epoch, device)
            
            result.write('epoch %d \n' % epoch)
            result.write('Train loss:'+ str(train_loss)+'\n')
            result.write('Test loss:'+ str(test_loss)+'\n')
            if (epoch >= params.eval_start and epoch % params.eval_freq == 0):
                result.write('-----evaluation ber:'+str(ber)+'\n')
            else:
                result.write('-----:no evaluation'+'\n')
            result.write('\n')
            result.flush()
            
            torch.save({
                'epoch': epoch+1,
                'arch': params.model_arch,
                'state_dict': model.state_dict(),
                'optimizer': optimizer.state_dict(),
            }, model_path, pickle_protocol=4)
        result.close()
    
def train(train_loader, model:BaseModel, optimizer, epoch, device):
    # switch to train mode
    model.train()
    
    train_loss = 0
    bt_cnt = 0
    for datas, labels in train_loader:
        datas, labels = datas.to(device), labels.to(device)
        
        optimizer.zero_grad()
        output = model(datas)
        loss = loss_func(output, labels, device)

        # compute gradient and do gradient step
        loss.backward()
        optimizer.step()
        train_loss += loss.item()
        bt_cnt += 1
    avg_loss = train_loss / bt_cnt

    # print
    if (epoch % params.print_freq_ep == 0):
        print('Train Epoch: {} Avg Loss: {:.6f}'.format(epoch+1, avg_loss))
    
    return avg_loss
            

def validate(test_loader, val_loader, model:BaseModel, epoch, device):
    # switch to evaluate mode
    model.eval()
        
    # network
    with torch.no_grad():
        test_loss = 0
        bt_cnt = 0
        for datas, labels in test_loader:
            datas, labels = datas.to(device), labels.to(device)
            
            output = model(datas)
            loss = loss_func(output, labels, device)

            test_loss += loss.item()
            bt_cnt += 1
        avg_loss = test_loss / bt_cnt
    
    if epoch % params.print_freq_ep == 0:
        print('Test Epoch: {} Avg Loss: {:.6f}'.format(epoch+1, avg_loss))
    
    # evaluation
    ber = 1.0
    if (epoch >= params.eval_start) & (epoch % params.eval_freq == 0):
        decodeword = np.empty((1, 0))
        label_val = np.empty((1, 0))
        for datas, labels in val_loader:
            dec = model.decode(params.eval_length, datas, device)
            decodeword = np.append(decodeword, dec, axis=1)
            labels = labels.numpy()[:, :params.eval_length].reshape(1, -1)
            label_val = np.append(label_val, labels, axis=1)
        ber = (np.sum(np.abs(decodeword - label_val))/label_val.shape[1])
        print('Validation Epoch: {} - ber: {}'.format(epoch+1, ber))
    
    return avg_loss, ber

def loss_func(output, label, device):
    return F.binary_cross_entropy(output, label).to(device)
        
if __name__ == '__main__':
    main()