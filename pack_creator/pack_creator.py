import math
import h5py
from shapely.geometry import Polygon
import scipy.io
import numpy as np

class State:
    def __init__(self, pos=[0, 0], theta=0, speed=[0, 0], rot=0):
        self.pos = pos
        self.theta = theta
        self.speed = speed
        self.rot = rot

    def get_dataset_slice(self):
      return [
        self.pos[0],
        self.pos[1],
        self.theta,
        self.speed[0],
        self.speed[1],
        self.rot,
        0,
        self.pos[0],
        self.pos[1]
      ]


class Floe:
  def __init__(self, shape, state=None):
    """
    Shape must be described in counter clockwise order !
    """
    # re-center shape on mass center
    c = Polygon(shape).centroid
    # self.shape = shape # As point list [(x, y), ...]
    # self.state = state or State() # State object
    self.shape = [(x - c.x, y - c.y) for x, y in shape]
    if state:
        x, y = state.pos
        state.pos = [x + c.x, y + c.y]
        self.state = state
    else:
        self.state = State()


def get_window(floes_list):
    max_x = max(pt[0] + floe.state.pos[0] for floe in floes_list for pt in floe.shape)
    max_y = max(pt[1] + floe.state.pos[1] for floe in floes_list for pt in floe.shape)
    min_x = min(pt[0] + floe.state.pos[0] for floe in floes_list for pt in floe.shape)
    min_y = min(pt[1] + floe.state.pos[1] for floe in floes_list for pt in floe.shape)
    width = max(max_x - min_x, max_y - min_y) * 1.01
    x0 = (min_x + max_x) / 2
    y0 = (min_y + max_y) / 2
    return [x0 - width / 2 , x0 + width / 2, y0 - width / 2, y0 + width / 2]


def write_input_file(floes_list, filename):
    """Creates hdf5 input file for floe list"""
    with h5py.File(f"io/inputs/{filename}.h5", "w") as f:
        states_dset = f.create_dataset("floe_states", (1, len(floes_list), 9), dtype='float64') # 1 = t0, nb_floe, state_size
        grp = f.create_group("floe_shapes")
        for i, floe in enumerate(floes_list):
            shape_dset = grp.create_dataset(f"{i}", (len(floe.shape), 2), dtype='float64') # nb_points, 2 (space dim)
            shape_dset[...] = floe.shape
            # shape_dset.attrs['thickness'] = 1.2
            states_dset[0, i, ...] = floe.state.get_dataset_slice()
        win_dset = f.create_dataset("window", (4, ), dtype='float64')
        win_dset[...] = get_window(floes_list)


def circle_floe_shape(radius=1, nb_vertices=25):
  """Regular polygon floe, centered on (0, 0)"""
  f = []
  for k in range(nb_vertices):
    f.append((
      radius * math.cos((2 * k * math.pi) / nb_vertices), 
      radius * math.sin((2 * k * math.pi) / nb_vertices)
    ))
  return f

def rectangle_floe_shape(xlen, ylen):
   x = xlen / 2
   y = ylen / 2
   return [(x, -y), (x, y), (-x, y), (-x, -y)]

def translate_floe_group(floes, x, y):
    for floe in floes:
        floe.state.pos[0] += x
        floe.state.pos[1] += y



def get_floes_from_bdd(filename, nPoints=25):
    """ Returns a list of floes, which are defined by a list of nPoints coordinates. They are all centered at the origin
    
    ex:     mat = get_floes_from_bdd('../path/to/Biblio_Floes.mat', 25)
            list_f = [] 
            floe = np.array(mat[iFloe])
            pos_x = 0
            pos_y = 0
            list_f.append(Floe(floe, State(pos=[pos_x, pos_y])))

    
    """
    biblio_floes = _discretize_biblio_floes(scipy.io.loadmat('../../../Floe/Floe_Cpp/io/inputs/Biblio_Floes.mat'), nPoints)
    return biblio_floes 


def _discretize_biblio_floes(mat , nMax=25):
    disc_biblio_floe = []
    for iFloe in np.arange(0, len(mat['G'])):
        floe = []
        n_max = min(nMax, len(mat['G'][iFloe][0]))
        floeMat = mat['G'][iFloe]
        for iPoint in np.arange(0,n_max):
            point = int(np.floor(len(mat['G'][iFloe][0])*iPoint/n_max)) 
            floe.append(np.array([floeMat[0][point,0], floeMat[0][point,1]]) - np.array([np.mean(mat['G'][iFloe][0][:,0]), 0]) - np.array([0, np.mean(mat['G'][iFloe][0][:,1])]))
        disc_biblio_floe.append(floe)
    return disc_biblio_floe 



def get_floes_from_output_file(filename, timing=-1):
    """ Returns a list of class Floe from a FloeDyn output, at the state corresponding to the specified time step (the latest by default)

    ex:     list_f = []
            # build the floe list list_f as you wish, list_f.append(Floe(truc truc))... 
            floes = get_floes_from_output_file('../path/to/io/outputs/out_9464522515578516354651f_99p.h5')
            list_f += floes
        
    """
    d = {}
    floes = []

    data_file = h5py.File(filename, 'r')
    file_time_dependant_keys =["time", "floe_states"] 
    nTime = timing 
    if data_file.get("time") is not None:
        if timing < 0:
            nTime = len(data_file.get("time"))-1
    else:
        print('could not find time in {}'.format(filename))
        return floes
    for key in file_time_dependant_keys:
        if data_file.get(key) is not None:
            d[key] = data_file.get(key)[nTime]
        else:
            print('could not find {} in {}'.format(key, filename))
            return floes
    if data_file.get("floe_shapes") is not None:
        d["floe_shapes"] = [np.array(data_file.get("floe_shapes").get(k)) for k in sorted(list(data_file.get("floe_shapes")), key=int)]
    else:
        print('could not find floe shapes in {}'.format(filename))
        return floes
    
    for iFloe in np.arange(0, len(d["floe_shapes"])):
        floes.append(Floe(d["floe_shapes"][iFloe], State(pos=[d["floe_states"][iFloe, 7], d["floe_states"][iFloe, 8]], speed=[0,0], theta=d["floe_states"][iFloe, 2])))

    return floes 

