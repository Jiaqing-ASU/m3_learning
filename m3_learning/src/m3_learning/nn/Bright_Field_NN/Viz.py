import matplotlib.pyplot as plt
from m3_learning.viz.layout import imagemap, add_scalebar
from m3_learning.util.file_IO import make_folder
from m3_learning.viz.layout import layout_fig
import numpy as np
import torch
import matplotlib.pyplot as plt
import matplotlib.patches as patches

from tqdm import tqdm
from os.path import join as pjoin
from m3_learning.viz.nn import embeddings as embeddings_

class Viz:

    def __init__(self,
                  dset,
                 channels=None,
                 color_map='viridis',
                 printer=None,
                 labelfigs_=False,
                 scalebar_=None,
                 ):
        """Initialization of the Viz class
        """

        self.printer = printer
        self.labelfigs_ = labelfigs_
        self.scalebar_ = scalebar_
        self.cmap = plt.get_cmap(color_map)
        self.channels = channels
        self.dset = dset


    def view_raw(self, img_name):
        data = self.dset.get_raw_img(*img_name)
        fig,axs = plt.subplots(figsize=(1.25,1.25))

        imagemap(axs, data, divider_ = True)

        axs.set_box_aspect(1)

        if self.scalebar_ is not None:
            # adds a scalebar to the figure
            add_scalebar(axs, self.scalebar_)

        if self.printer is not None:
              self.printer.savefig(fig,
                                     f'{img_name[0]}_{img_name[1]}_raw', tight_layout=False,showfig=True)


    def view_window(self,t,x,y,name,condition,
                    window_parms={  'fft_mode': 'abs',
                                    'interpol_factor': 2.3,
                                    'mode': 'fft',
                                    'window_size_x': 128,
                                    'window_size_y': 128,
                                    'window_step_x': 32,
                                    'window_step_y': 32,
                                    'zoom_factor': 2 }):
        '''
        plot the filtered image, transform, and window
        
        Args:
            x (int): x tile
            y (int): y tile
            name (str): name given to preprocessing h5 file, which is named '(name)_preprocessed.h5'
            condition (str): "Ramp_up' or 'Ramp_Down'
        '''

        h = self.dset.open_combined_h5(name)
        image = h['All_filtered']

        # Make grid
        # fig = plt.figure(figsize=(16,8))
        fig = plt.figure()
        gs = fig.add_gridspec(2, 3)
        axs = []
        axs.append( fig.add_subplot(gs[:,0:2]) ) # large subplot (2 rows, 2 columns)
        axs.append( fig.add_subplot(gs[0,2]) )   # small subplot (1st row, 3rd column)
        axs.append(fig.add_subplot(gs[1,2]))

        idx,bbox = self.dset.get_window_indx(t,x,y,name=name)
        print(idx,bbox)
        
        # grp[idx,0], orig[t,bbox[0]:bbox[1], bbox[2]:bbox[3]]
        
        # plot the full image
        rect = patches.Rectangle((bbox[0],bbox[2]), bbox[1]-bbox[0],bbox[3]-bbox[2],
                                 linewidth=2, edgecolor='r', facecolor='none')
        axs[0].set_title('Full Image')
        axs[0].add_patch(rect)
        imagemap(axs[0],image[t],colorbars=True)
        
        # a1 = axs[0].imshow(image[:])
        # rect = patches.Rectangle((xi+32,yi+32),64,64,linewidth=2, edgecolor='r', facecolor='none')
        # divider = make_axes_locatable(axs[0])
        # cax = divider.append_axes('right', size='5%')
        # cb=fig.colorbar(a1, cax=cax, orientation='vertical', pad = 0.2)
        # cb.ax.xaxis.set_ticks_position('top')
        # cb.ax.xaxis.set_label_position('top')

        axs[1].set_title('FFT tile')
        imagemap(axs[1],h['windows']['windows_logdata'][idx,0],colorbars=True)

        # a2 = axs[1].imshow((np.log(fft)))
        # divider = make_axes_locatable(axs[1])
        # cax = divider.append_axes('right', size='5%')
        # cb=fig.colorbar(a2, cax=cax, orientation='vertical', pad = 0.2)
        # cb.ax.xaxis.set_ticks_position('top')
        # cb.ax.xaxis.set_label_position('top')

        # fft = dask.array.rechunk(fft,-1)
        # ifft = np.fft.ifft2(fft).real
        axs[2].set_title('Image tile')
        imagemap(axs[2],image[t,bbox[0]:bbox[1],bbox[2]:bbox[3]],colorbars=True)

        # a3 = axs[2].imshow(image[xi:xi+64,yi:yi+64],vmax=1.,vmin=0.)
        # divider = make_axes_locatable(axs[2])
        # cax = divider.append_axes('right', size='5%')
        # cb=fig.colorbar(a3, cax=cax, orientation='vertical', pad = 0.2)
        # cb.ax.xaxis.set_ticks_position('top')
        # cb.ax.xaxis.set_label_position('top')

        plt.tight_layout()
        plt.show()


# TODO:
# widget to see all temps for 1) raw 2) filtered 3) unfiltered