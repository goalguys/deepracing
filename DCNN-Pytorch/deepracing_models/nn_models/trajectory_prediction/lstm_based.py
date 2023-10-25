import torch.nn as nn 
import torch.nn.functional as F
import torch
import collections

### 
# BezierMixNet is a modified version of MixNet, published by Phillip Karle & Technical University of Munich on August 22, 2022 under GNU General Public License V3.
# Modified on various dates starting April 14, 2023
###  
class BezierMixNet(nn.Module):

    def __init__(self, params : dict):
        """Initializes a BezierMixNet object."""
        super(BezierMixNet, self).__init__()
        self._params = params

        input_embedding : dict = params["input_embedding"]
        input_dimension = 2
        if input_embedding["velocity"]:
            input_dimension+=2
        if input_embedding["quaternion"]:
            input_dimension+=2
        if input_embedding["heading_angle"]:
            input_dimension+=1
        input_hidden_layers = input_embedding.get("hidden_layers", None)
        if input_hidden_layers is None:
            self._inp_emb = torch.nn.Linear(input_dimension, params["encoder"]["in_size"])
        else:
            self._inp_emb = self._get_linear_stack(input_dimension, input_hidden_layers, params["encoder"]["in_size"], "input_embedder")
        # History encoder LSTM:
        self._enc_hist = torch.nn.LSTM(
            params["encoder"]["in_size"],
            params["encoder"]["hidden_size"],
            1,
            batch_first=True,
        )
        if params.get("separate_boundary_embedder", False):
            boundary_embedding : dict = params["boundary_embedding"]
            boundary_dimension = 2
            if boundary_embedding["tangent"]:
                boundary_dimension+=2
            # if boundary_embedding["curvature"]:
            #     boundary_dimension+=1
            boundary_hidden_layers = boundary_embedding.get("hidden_layers", None)
            if boundary_hidden_layers is None:
                self._boundary_emb = torch.nn.Linear(boundary_dimension, params["encoder"]["in_size"])
            else:
                self._boundary_emb = self._get_linear_stack(boundary_dimension, boundary_hidden_layers, params["encoder"]["in_size"], "boundary_embedder")
        else:
            self._boundary_emb = self._inp_emb
        # Boundary encoders:
        self._enc_left_bound = torch.nn.LSTM(
            params["encoder"]["in_size"],
            params["encoder"]["hidden_size"],
            1,
            batch_first=True,
        )

        self._enc_right_bound = torch.nn.LSTM(
            params["encoder"]["in_size"],
            params["encoder"]["hidden_size"],
            1,
            batch_first=True,
        )

        # Linear stack that outputs the path mixture ratios:
        self._mix_out_layers = self._get_linear_stack(
            in_size=params["encoder"]["hidden_size"] * 3,
            hidden_sizes=params["mixer_linear_stack"]["hidden_sizes"],
            out_size=params["mixer_linear_stack"]["out_size"],
            name="mix",
        )

        acc_decoder_embedder_layers = params["acc_decoder"].get("embedder_layers", None)
        # dynamic embedder between the encoder and the decoder:
        if acc_decoder_embedder_layers is None:
            self._dyn_embedder = nn.Linear(
                params["encoder"]["hidden_size"] * 3, params["acc_decoder"]["in_size"]
            )
        else:
            self._dyn_embedder = self._get_linear_stack(
            in_size=params["encoder"]["hidden_size"] * 3,
            hidden_sizes=acc_decoder_embedder_layers,
            out_size=params["acc_decoder"]["in_size"],
            name="decoder_embedder",
            )

        # acceleration decoder:
        self._acc_decoder = nn.LSTM(
            params["acc_decoder"]["in_size"],
            params["acc_decoder"]["hidden_size"],
            1,
            batch_first=True,
        )
        
        acc_decoder_output_layers = params["acc_decoder"].get("output_layers", None)        
        # output linear layer of the acceleration decoder:
        if acc_decoder_output_layers is None:
            self._acc_out_layer = nn.Linear(params["acc_decoder"]["hidden_size"], 1)
        else:
            self._acc_out_layer = self._get_linear_stack(
                in_size=params["acc_decoder"]["hidden_size"],
                hidden_sizes=acc_decoder_output_layers,
                out_size=1,
                name="acc_decoder_output",
            )


        self._acc_final_layer_tanh = params["acc_decoder"]["final_layer_tanh"]

        use_bias = True
        self._final_linear_layer = nn.Linear(4,4, bias=use_bias)
        if params["mixer_linear_stack"]["final_affine_transform"]: #.get("final_affine_transform", True):
            self._final_linear_layer.weight = torch.nn.Parameter(torch.eye(4) + 0.0001*torch.randn(4,4))
            self._final_linear_layer.bias = torch.nn.Parameter(0.0001*torch.randn(4))
        else:
            #Effectively make this layer do nothing.
            self._final_linear_layer.weight = torch.nn.Parameter(torch.eye(4))
            self._final_linear_layer.bias = torch.nn.Parameter(torch.ones(4))
            self._final_linear_layer.requires_grad_(False)

        
        # self.constrain_derivs : bool = self._params["acc_decoder"]["constrain_derivatives"]
        
        kbeziervel = self._params["acc_decoder"]["kbeziervel"] 
        num_accel_sections = self._params["acc_decoder"]["num_acc_sections"] 
        num_transitions = num_accel_sections - 1
        constraints_per_transition =  1
        coefs_per_segment = kbeziervel + 1
        self.num_velocity_coefs : int = num_accel_sections*coefs_per_segment - constraints_per_transition*num_transitions - 1

        if use_bias:
            self._final_linear_layer.bias = torch.nn.Parameter(0.0001*torch.randn(4))
        # migrating the model parameters to the chosen device:
        if params["gpu_index"]>=0 and torch.cuda.is_available():
            self.device = torch.device("cuda:%d" % (params["gpu_index"],))
            print("Using CUDA as device for BezierMixNet")
        else:
            self.device = torch.device("cpu")
            print("Using CPU as device for BezierMixNet")
        
        self.to(self.device)

    def forward(self, hist, left_bound, right_bound):
        """Implements the forward pass of the model.

        args:
            hist: [tensor with shape=(batch_size, hist_len, hist_dim)]
            left_bound: [tensor with shape=(batch_size, boundary_len, 2)]
            right_bound: [tensor with shape=(batch_size, boundary_len, 2)]

        returns:
            mix_out: [tensor with shape=(batch_size, out_size)]: The path mixing ratios in the order:
                left_ratio, right_ratio, center_ratio, race_ratio
            acc_out: [tensor with shape=(batch_size, num_acc_sections)]: The accelerations in the sections
        """
        hist_embedded = self._inp_emb(hist)
        # encoders:
        all_hist_h, (hist_h, _) = self._enc_hist(hist_embedded)

        lb_embedded = self._boundary_emb(left_bound)
        all_left_h, (left_h, _) = self._enc_left_bound(lb_embedded)
        
        rb_embedded = self._boundary_emb(right_bound)
        all_right_h, (right_h, _) = self._enc_right_bound(rb_embedded)

        # concatenate and squeeze encodings: 
        enc = torch.squeeze(torch.cat((hist_h, left_h, right_h), 2), dim=0)

        # path mixture through softmax:
        mix_out_softmax = torch.softmax(self._mix_out_layers(enc), dim=1)
        mix_out = self._final_linear_layer(mix_out_softmax)

        # acceleration decoding:
        dec_input = torch.relu(self._dyn_embedder(enc)).unsqueeze(dim=1)
        dec_input = dec_input.repeat(
            1, self.num_velocity_coefs, 1
        )

        acc_out, _ = self._acc_decoder(dec_input)
        acc_out = torch.squeeze(self._acc_out_layer(torch.relu(acc_out)), dim=2)
        if self._acc_final_layer_tanh:
            acc_out = torch.tanh(acc_out) * self._params["acc_decoder"]["max_acc"]
        return mix_out, acc_out

    def load_model_weights(self, weights_path):
        self.load_state_dict(torch.load(weights_path, map_location=self.device))
        print("Successfully loaded model weights from {}".format(weights_path))

    def _get_linear_stack(
        self, in_size: int, hidden_sizes: list, out_size: int, name: str
    ):
        """Creates a stack of linear layers with the given sizes and with relu activation."""

        layer_sizes = []
        layer_sizes.append(in_size)  # The input size of the linear stack
        layer_sizes += hidden_sizes  # The hidden layer sizes specified in params
        layer_sizes.append(out_size)  # The output size specified in the params

        layer_list = []
        for i in range(len(layer_sizes) - 1):
            layer_name = name + "linear" + str(i + 1)
            act_name = name + "relu" + str(i + 1)
            layer_list.append(
                (layer_name, nn.Linear(layer_sizes[i], layer_sizes[i + 1]))
            )
            layer_list.append((act_name, nn.ReLU()))

        # removing the last ReLU layer:
        layer_list = layer_list[:-1]

        return nn.Sequential(collections.OrderedDict(layer_list))

    def get_params(self):
        """Accessor for the params of the network."""
        return self._params