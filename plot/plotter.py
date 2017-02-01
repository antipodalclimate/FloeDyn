#!/usr/bin/env python
# -*- coding: utf-8 -*-
import numpy as np
# import matplotlib
# matplotlib.use("GTKAgg")
from matplotlib import transforms, cm, animation, colors, gridspec
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
from matplotlib.collections import PatchCollection, PolyCollection

from multiprocessing import Pool, Process, cpu_count
from subprocess import call

from utils import filename_without_extension, get_unused_path
import h5py
import datetime


class FloeVideoPlotter(object):
    """ Drawing floes from simulation output files """

    def __init__(self, options):
        self.OPTIONS = options
        self.writer = animation.FFMpegWriter(fps=30, metadata=dict(artist='Me'), extra_args=None)#, codec="libx264", bitrate=32000

    def do(self):
        funcs = {
            "anim" : self.plot_floes,
            "mkvid" : self.plot_floes_fast,
            "img" : self.plot_one,
        }
        if self.OPTIONS.codec:
            self.writer.codec = "lib{}".format(self.OPTIONS.codec)
            # writer.extra_args = ['-profile:v', 'high444', '-tune:v', 'animation', '-preset:v', 'slow', '-level', '4.0', '-x264opts', 'crf=18']
            self.writer.extra_args = ['-profile:v', 'high444', '-tune:v', 'animation', '-preset:v', 'slow', '-level', '4.0']
        funcs[self.OPTIONS.function](**vars(self.OPTIONS))

    def get_final_video_path(self, input_file_path, video_ext="mp4"):
        filename = filename_without_extension(input_file_path)
        return get_unused_path(u'io/videos/{}.{}'.format(filename, video_ext))

    def _init2(self, data, ax, begin=0):
        "initializes floes (Polygon creation) for matplotlib animation creation (v3 : shapes)"
        floes_collec = PolyCollection(data.get("floe_shapes"), linewidths=0.2,
                                     cmap=cm.YlOrRd, norm=colors.PowerNorm(gamma=0.3))
                                    # cmap=cm.Paired)#MPI
        if getattr(self.OPTIONS, "color", True):
            floes_collec.set_array(data.get("impulses")[begin])
            floes_collec.set_clim([0, data["MAX_IMPULSE"]])
            plt.colorbar(floes_collec, ax = ax, fraction = 0.05) # display color bar
        else:
            floes_collec.set_array(np.zeros(len(data.get("floe_shapes"))))
        # ax.axes.get_yaxis().set_visible(False) # remove x axis informations
        ax.add_collection(floes_collec)

        if getattr(self.OPTIONS, "ghosts", False):
            ghosts_collec = PolyCollection(data.get("floe_shapes") * 8, linewidths=0.2, alpha=0.4,
                                         cmap=cm.YlOrRd, norm=colors.PowerNorm(gamma=0.3))
                                        # cmap=cm.Paired)#MPI
            ghosts_collec.set_clim(floes_collec.get_clim())
            ghosts_collec.set_array(np.zeros(len(data.get("floe_shapes")) * 8))
            ax.add_collection(ghosts_collec)

        # Display generator window
        if getattr(self.OPTIONS, "disp_window"):
            w = data.get("window")
            if w:
                ax.add_patch( Polygon(((w[0], w[2]), (w[0], w[3]), (w[1], w[3]), (w[1], w[2])),
                              True, facecolor=None, alpha=0.2,
                              edgecolor="white", linewidth=0.2))
        # END Display generator window

        return ax


    def _init2_dual(self, data, ax1, ax2, begin=0):
        "initializes floes (Polygon creation) for matplotlib animation creation (v3 : shapes)"
        ax1 = _init2(data, ax1)
        first_idx, _ = data["total_trunk_indices"]
        x = np.array(data.get("total_time")[0:first_idx])
        ys = [np.array([data.get("total_impulses")[i][idx] for i in range(len(x))]) for idx in data.get("special_indices", [])]
        for y in ys:
            ax2.plot(x,y)
        ax2.axis([data.get("total_time")[0], data.get("total_time")[-1], -100, data["MAX_IMPULSE"]])
        ax2.set_title("Norm of the contact impulses applied to the obstacle")
        # ax.set_xlabel("text") # bottom
        return ax1, ax2


    def _init1(self, data, ax, begin=0):
        "initializes floes (Polygon creation) for matplotlib animation creation"
        for (i,s) in data.get("floe_outlines").iteritems():
            special = i=="1500"
            polygon = Polygon(s[begin],
                              True,
                              facecolor="#FFF7ED" if not special else "#FA9A50",
                              linewidth=0.2,
                              hatch="" if not special else "x")
            ax.add_patch(polygon)
        return ax

    def _update2(self, num, data, ax, step=1, begin=0):
        """updates floes (Polygons) positions for matplotlib animation creation
        (version 3 : collection and compute outlines transforms"""
        indic = begin + step * num
        opt_ghosts, opt_color, opt_follow = (
            getattr(self.OPTIONS, opt) for opt in ["ghosts", "color", "follow"]
        )

        verts = self._transform_shapes(data.get("floe_shapes"), data.get("floe_states")[indic], opt_follow)
        ax.collections[0].set_verts(verts)

        if opt_ghosts:
            ghosts_verts = [v for trans in d["ghosts_trans"] for v in translate_group(verts, trans)]
            ax.collections[1].set_verts(ghosts_verts)

        if opt_color:
            ax.collections[0].set_array(data.get("impulses")[indic])
            if opt_ghosts:
                ax.collections[1].set_array(np.tile(data.get("impulses")[indic], 8))
        ax.set_title("t = {}".format(str(datetime.timedelta(seconds=int(data.get("time")[indic])))))
        if not data.get("static_axes"):
            # ax.axis('equal')
            ax.relim()
            ax.autoscale_view(True,True,True)
        if opt_follow:
            axes = data.get("static_axes")
            ax.set_xlim(data.get("mass_center")[indic][0] + axes[0], data.get("mass_center")[indic][0] +  axes[1])
            ax.set_ylim(data.get("mass_center")[indic][1] + axes[2], data.get("mass_center")[indic][1] +  axes[3])
        # # begin MPI zones
        # ax.collections[0].set_clim([0, 9])
        # ax.collections[1].set_clim([0, 9])
        # W, H = ax.get_xlim()[1] - ax.get_xlim()[0], ax.get_ylim()[1] - ax.get_ylim()[0]
        # N = 6
        # WZ, HZ = W/N, H/N
        # ax.collections[0].set_array(np.array([(int((x[0] - ax.get_xlim()[0]) / WZ) + int((x[1] - ax.get_ylim()[0]) / HZ) * N)%9 for x in data.get("floe_states")[indic]]))
        # ghosts_trans = [(i * w, j * w) for i in range(-2, 3) for j in range(-2, 3) if not i==j==0]
        # gstates = [(x[0] + i, x[1] + j) for i,j in ghosts_trans for x in data.get("floe_states")[indic]]
        # ax.collections[1].set_array(np.array([(int((x[0] - ax.get_xlim()[0]) / WZ) + int((x[1] - ax.get_ylim()[0]) / HZ) * N)%9 for x in gstates]))
        # # end MPI zones
        return ax,

    def _update2_dual(self, num, data, ax1, ax2, step=1, begin=0):
        first_idx, _ = data["total_trunk_indices"]
        indic = first_idx + num
        ax1, = _update2(num, data, ax1)
        for i, idx in enumerate(data.get("special_indices")):
            ax2.lines[i].set_xdata(np.append(ax2.lines[i].get_xdata(), data.get("total_time")[indic]))
            ax2.lines[i].set_ydata(np.append(ax2.lines[i].get_ydata(), data.get("total_impulses")[indic][idx]))
        return ax1, ax2


    def _transform_shapes(self, floe_shapes, floe_states, follow=False):
        resp = floe_shapes
        def rotation_mat(theta):
            return np.array([[np.cos(theta), -np.sin(theta)], 
                             [np.sin(theta),  np.cos(theta)]])
        rots = [rotation_mat(x[2]) for x in floe_states]
        resp = [np.transpose(np.dot(rot, np.transpose(shape))) for rot, shape in zip(rots, floe_shapes)]
        pos_ids = (0,1) if follow else (7,8) # (7,8) contains translated position in fixed initial window
        resp = [np.add(shape, np.repeat([[x[pos_ids[0]], x[pos_ids[1]]]], len(shape), axis=0)) for x, shape in zip(floe_states, resp)]
        return resp

    def translate_group(self, vertices, trans):
        return [np.add(shape, np.repeat([[trans[0], trans[1]]], len(shape), axis=0)) for shape in vertices]

    def _update1(self, num, data, ax, step=1, begin=0):
        "updates floes (Polygons) positions for matplotlib animation creation"
        indic = begin + step * num
        for i, s in enumerate(data.get("floe_outlines").itervalues()):
            ax.patches[i].set_xy(s[indic])
        ax.set_title("t = {}".format(str(datetime.timedelta(seconds=int(data.get("time")[indic])))))
        if not data.get("static_axes"):
            ax.axis('equal')
            ax.relim()
            ax.autoscale_view(True,True,True)
        return ax,

    def anim_fcts(self, version):
        d = {1: (self._init1,self._update1), 2: (self._init2,self._update2)}
        return d[version]

    def plot_floes(self, filename="out", step=1, version=2, make_video=1, **kwargs):
        "displays floes animation from hdf5 output file (simple plot or video creation)"
        data_file    = h5py.File(filename, 'r')
        # Read Usefull data from file
        data_global = self._get_useful_datas(data_file, step, version)
        fig, ax = plt.subplots()
        if getattr(self.OPTIONS, "hd", False):
            fig.set_size_inches(20, 15)
            fig.set_dpi(100)
        init, update = self.anim_fcts(version)
        ax = init(data_global, ax)
        if not data_global.get("static_axes"):
            ax.axis('equal') # automatic scale
        else:
            ax.axis(data_global.get("static_axes"))
        ax.set_axis_bgcolor('#162252')
        anim = animation.FuncAnimation(
            fig, update, len(data_global.get("time")), fargs=(data_global, ax),
            interval=1, blit=False)
        if make_video:
            anim.save(self.get_final_video_path(filename), writer=self.writer)
        else:
            plt.show()


    def plot_one(self, filename, **kwargs):
        "displays floes at last time recorded in output file"
        init, update = self.anim_fcts(2)
        file    = h5py.File(filename, 'r')
        fig, ax = plt.subplots()
        idx = int(raw_input("Time index (-1 for last one) : "))
        num = idx if idx != -1 else data_global.get("time").size - 1 # TODO data_global not declared !!
        
        data_global = self._get_useful_datas(file, 0, 2, num)
        ax = init(data_global, ax)
        ax.axis('equal')
        ax.set_axis_bgcolor('#162252') 
        ax, = update(0, data_global, ax)
        plt.show()


    #############################
    # Parallel video creation : #
    #############################

    def make_partial_floe_video(self, out_filename, data_chunk, version):
        "creates video directly from data"
        print 1
        fig, ax = plt.subplots()
        print 2
        if getattr(self.OPTIONS, "hd", False):
            fig.set_size_inches(20, 15)
            fig.set_dpi(100)
        print 3
        init, update = self.anim_fcts(version)
        ax = init(data_chunk, ax)
        print 4
        if not data_chunk.get("static_axes"):
            ax.axis('equal') # automatic scale
        else:
            ax.axis(data_chunk.get("static_axes"))
        print 5
        ax.set_axis_bgcolor('#162252')
        anim = animation.FuncAnimation(
            fig, update, len(data_chunk.get("time")), fargs=(data_chunk, ax),
            interval=1, blit=False)
        print 6
        print out_filename
        anim.save(out_filename, writer=self.writer)

    def make_partial_floe_video_helper(self, t):
        return self.make_partial_floe_video(*t)


    def make_partial_floe_video_dual_plot(self, out_filename, data_chunk, version):
        "creates video directly from data, and adds obstacle impulse subplot under floes"
        gs = gridspec.GridSpec(2, 1, height_ratios=[3, 1])
        fig = plt.figure()
        if getattr(self.OPTIONS, "hd", False):
            fig.set_size_inches(16, 12)
            fig.set_dpi(100)
        ax1 = plt.subplot(gs[0])
        ax2 = plt.subplot(gs[1])
        init, update = _init2_dual, _update2_dual
        ax1, ax2 = init(data_chunk, ax1, ax2)
        if not data_chunk.get("static_axes"):
            ax1.axis('equal') # automatic scale
        else:
            ax1.axis(data_chunk.get("static_axes"))
        ax1.set_axis_bgcolor('#162252')
        anim = animation.FuncAnimation(
            fig, update, len(data_chunk.get("time")), fargs=(data_chunk, ax1, ax2),
            interval=50, blit=False)
        anim.save(out_filename, writer=self.writer)

    def make_partial_floe_video_dual_plot_helper(self, t):
        return self.make_partial_floe_video_dual_plot(*t)

    def plot_floes_fast(self, filename="out", step=1, version=2, dual=False, **kwargs):
        "Creates a video from hdf5 file output, using multiprocessing to go faster"
        data_file    = h5py.File(filename, 'r')
        nb_step = int(ceil(len(data_file.get("time")) / step))
        # Create multiple partial videos
        trunks = self._get_trunks(nb_step)
        nb_process = len(trunks)
        temp_dir = 'plot_tmp'
        call(['mkdir', temp_dir])
        partial_file_names = ["{}/{}.mpg".format(temp_dir, i) for i in range(nb_process)]
        # Read Usefull data from file
        data_global = self._get_useful_datas(data_file, step, version)
        # Build trunks datas
        L = [( partial_file_names[i],
               self._get_useful_trunk_datas(data_global, trunk, version),
                version ) for i,trunk in enumerate(trunks)]
        # Launch process pool 
        p = Pool(nb_process)
        partial_video_maker = self.make_partial_floe_video_helper if not dual else make_partial_floe_video_dual_plot_helper
        p.map(partial_video_maker, L)
        p.close()
        p.join()
        # Concat all partial video
        out_filename = self.get_final_video_path(filename)
        call(['ffmpeg',  '-i', 'concat:{}'.format("|".join(partial_file_names)), '-c', 'copy', out_filename])
        call(['rm', '-r', temp_dir])


    def _get_useful_datas(self, data_file, step, version, single_step="OFF"):
        d = {}
        # File datas
        file_time_dependant_keys =["time", "floe_states", "mass_center"]
        if single_step == "OFF":
            for key in file_time_dependant_keys:
                d[key] = data_file.get(key)[::step]
        else:
            for key in file_time_dependant_keys:
                d[key] = data_file.get(key)[single_step:single_step+1]
        d["total_time"] = d["time"]
        if version == 1:
            d["floe_outlines"] = {k : dataset[::step]
                for k, dataset in data_file.get("floe_outlines").iteritems()}
        elif version == 2:
            if data_file.get("floe_shapes") is not None:
                d["floe_shapes"] = [np.array(data_file.get("floe_shapes").get(k)) for k  in sorted(list(data_file.get("floe_shapes")), key=int)]
            else:
                d["floe_shapes"] = self.calc_shapes(data_file)
        # Other datas
        d["impulses"] = d["total_impulses"] = self.calc_impulses(d["floe_states"], 6) # Calc impulsions
        # d["impulses"] = [np.zeros(len(d["floe_states"][0]))] * len(d["floe_states"]) # set impulses to 0
        # calc or set global max impulse for color range
        d["MAX_IMPULSE"] = max(np.amax(step_impulses) for step_impulses in d.get("impulses"))
        # Set static axes from window data
        w = data_file.get("window")
        w_width, w_length = w[1] - w[0], w[3] - w[2]
        d["static_axes"] = self.OPTIONS.static_axes
        if not d["static_axes"]:
            d["static_axes"] = [w[0] - w_width/4, w[1] + w_width/4, w[2] - w_length/4, w[3] + w_length/4]
            # d["static_axes"] = [w[0] - w_width*2, w[1] + w_width*2, w[2] - w_length*2, w[3] + w_length*2] #MPI bigger domain
        d["window"] = list(data_file.get("window", None))
        if getattr(self.OPTIONS, "ghosts"):
            d["ghosts_trans"] = [(i * w_width, j * w_length) for i in range(-1, 2) for j in range(-1, 2) if not i==j==0]
            # d["ghosts_trans"] = [(i * w, j * w) for i in range(-2, 3) for j in range(-2, 3) if not i==j==0] #MPI, more ghosts
        d["special_indices"] = getattr(self.OPTIONS, "index", [])
        return d


    def _get_useful_trunk_datas(self, data_global, trunk, version):
        """Slice global datas for a partial video"""
        d = {}
        trunked_keys = ["time", "floe_states", "impulses", "mass_center"]
        global_keys = [
            "total_time","total_impulses", "MAX_IMPULSE", "window",
            "special_indices", "static_axes", "ghosts_trans"
        ]
        for key in trunked_keys:
            d[key] = data_global.get(key)[trunk[0] : trunk[1]]
        for key in global_keys:
            d[key] = data_global.get(key)
        d["total_trunk_indices"] = (trunk[0], trunk[1])
        if version == 1:
            d["floe_outlines"] = {k : dataset[trunk[0] : trunk[1]]
                for k, dataset in data_global.get("floe_outlines").iteritems()}
        elif version == 2:
            d["floe_shapes"] = data_global.get("floe_shapes")
        return d


    def calc_impulses(self, floe_states, n=1):
        "calcul floe received impulses between each step and step -n"
        imps = [np.array([state[6] for state in time_states]) for time_states in floe_states]
        imps = [np.subtract(imps[t], imps[max(t-n, 0)]) for t in range(len(imps))]
        # for imp in imps: # hide bad values
        #     np.putmask(imp, imp>1e6, 0)
        for i in range(len(imps)):
            if np.amax(imps[i]) > 1e8:
                imps[i] = imps[i-1]
        return imps


    def calc_shapes(self, data):
        "calculate floe shapes (in relative frame) from outline and state"
        def rotation_mat(self, theta):
            return np.array([[np.cos(theta), -np.sin(theta)], 
                             [np.sin(theta),  np.cos(theta)]])
        resp = [np.array(data.get("floe_outlines").get(k)[0]) for k  in sorted(list(data.get("floe_outlines")), key=int)]
        resp = [np.add(shape, np.repeat([[-x[0], -x[1]]], len(shape), axis=0)) for x, shape in zip(data.get("floe_states")[0], resp)]
        rots = [rotation_mat(-x[2]) for x in data.get("floe_states")[0]]
        resp = [np.transpose(np.dot(rot, np.transpose(shape))) for rot, shape in zip(rots, resp)]
        return resp


    def _get_trunks(self, nb_steps):
        nb_process = min(cpu_count(), max(nb_steps / 5, 1))
        resp = []
        trunk_size = nb_steps / nb_process
        trunk_rest = nb_steps % nb_process
        j = 0
        for i in range(nb_process):
            add = 1 if i < trunk_rest else 0
            resp.append((j, j + trunk_size + add))
            j += trunk_size + add
        return resp
