import sys
import os
import torch
import torch.nn as nn

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.abspath(__file__))))))
from lib.Params import Params
from lib.Utils import codeword_threshold
sys.path.pop()

class BaseModel(nn.Module):
    def __init__(self, params:Params, device):
        super(BaseModel, self).__init__()
        self.params = params
        self.device = device
        self.time_step = params.pre_overlap_length + params.eval_length + params.post_overlap_length
        
    def forward(self, x):
        pass
    
    def decode(self, data_eval, hidden_state):
        dec = torch.zeros((data_eval.shape[0], 0)).float().to(data_eval.device)
        with torch.no_grad():
            decodeword, hidden_state = self.forward(data_eval, hidden_state)
            dec_block = codeword_threshold(decodeword)
            # concatenate the decoding codeword
            dec = torch.cat((dec, dec_block), 1)
            
        return dec.cpu().numpy().reshape(1, -1), hidden_state
    
    def init_weights(self, m):
        if type(m) == nn.Linear:
            nn.init.xavier_uniform_(m.weight)