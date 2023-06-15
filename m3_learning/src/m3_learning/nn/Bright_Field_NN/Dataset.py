import numpy as np
import hyperspy.api as hs
import os
import h5py
from skimage.color import rgb2gray
from scipy import ndimage
from sklearn.preprocessing import MinMaxScaler
import skimage
from tqdm import tqdm
import imageio
from pprint import pprint
import time
import math

# Pycroscopy
import sidpy
import pyNSID
# print('sidpy version: ', sidpy.__version__)
import pycroscopy as px
from pycroscopy.image import ImageWindowing
import dask.array as da

class Bright_Field_Dataset:

    def __init__(self, path, filename, verbose=False):

        self.path = path
        self.filename = filename
        self.verbose = verbose

        # make list of file names for original bright field images
        self.temps = self.get_temps()
        self.t_len = len(self.temps)
        
        if self.verbose:
            print('number of images: ', self.t_len)

    def temp(self, e):
        '''
        Gets temperature from file in format temp.png and determines ramp up or down
        '''
        if len(e) < 8:
            return '-'+e[:-4].zfill(3)
        else:
            return '-0.png'

    def list_imgs(self):
        l = [file.split('/')[-2] + ' ' + file.split('/')[-1][:-4] for file in self.temps]
        # pprint(l)
        return l

    def get_raw_img(self, state, temperature):
        """_summary_

        Args:
            state (_type_): "Ramp_Up" or "Ramp_Down"
            temperature (_type_): _description_
        """        
        s = f"{self.path}/{state}/{temperature}.png"
        im = rgb2gray(imageio.imread(s))
        return im


    def get_index(self):
        pass

    def get_temps(self):
        """gets list of paths to files of all temperatures

        Returns:
            list: paths to files of all temperatures, sorted by order they were taken
        """
        up = os.listdir(f'{self.path}/Ramp_Up')
        up.sort(key=self.temp)
        up = list(map(lambda x: f'{self.path}/Ramp_Up/'+x, up))

        down = os.listdir(f'{self.path}/Ramp_Down')
        down.sort(key=self.temp, reverse=True)
        down = list(map(lambda x: f'{self.path}/Ramp_Down/'+x, down))

        temps = up+down
        return temps
    
    def open_combined_h5(self,name):
        """_summary_

        Args:
            name (_type_): _description_

        Returns:
            _type_: _description_
        """        
        if len(name) > 0:
            name += '_'
        combined = self.path +"/" + name + 'preprocessed.h5'
        return h5py.File(combined,'a')

    def get_window_indx(self,t,a,b,name='',
                      windows_group = '',
                      dset_name = '',
                      logset_name = '',):
        """gets the scan from temperature idx t and point a,b, on the sample.

        Args:
            t (_type_): _description_
            a (_type_): _description_
            b (_type_): _description_
            name (str, optional): _description_. Defaults to ''.
            windows_group (str, optional): _description_. Defaults to ''.
            dset_name (str, optional): _description_. Defaults to ''.
            logset_name (str, optional): _description_. Defaults to ''.
            filtered (bool, optional): _description_. Defaults to True.

        Returns:
            idx (integer):
            bbox (list):
        """        
        h = self.open_combined_h5(name)
        windows_group+='windows'
        dset_name+='windows_data'
        logset_name+='windows_logdata'

        # try:
        grp = h[windows_group][logset_name]
        orig = h['All_filtered']
        t_,ox,oy = orig.shape
        _,a_,b_,_,_ = grp.attrs['orig_shape']
        x_ = int(np.ceil(grp.attrs['window_size_x']/2))
        y_ = int(np.ceil(grp.attrs['window_size_y']/2))
        x = x_ + a*grp.attrs['window_step_x']
        y = x_ + b*grp.attrs['window_step_y']

        idx = t*a_*b_+a_*a+b
        bbox = [x-x_, x+x_, y-y_, y+y_]
        return idx, bbox


        # except:
        #     print('Shape mismatch, or you have not generated windows yet')


    def write_h5(self, c1, c2, step, name=""):
        """Creates h5_file if it doesn't already exist. Crops raw data and create a dataset with and without Gaussian filtering.

        Args:
            c1 (_type_): _description_
            c2 (_type_): _description_
            step (_type_): _description_
            name (str, optional): _description_. Defaults to "".
        """

        # put the name of the file you would like to use
        h = self.open_combined_h5(name)
        t_len = len(self.temps)

        if 'All' in h.keys():
            del h['All']
        
        h_write = h.create_dataset('All', (t_len, step, step), dtype='f4')

        if 'All_filtered' in h.keys():
            del h['All_filtered']
        
        h_writef = h.create_dataset(
                'All_filtered', (t_len, step, step), dtype='f4')

        for i, temp_ in enumerate(tqdm(self.temps)):
            im = rgb2gray(imageio.imread(temp_))
            im1 = im[c1:c1+step, c2:c2+step]  # crop

            h_write[i] = im1

            img_blur = ndimage.gaussian_filter(im1, 20)
            im1 = im1-img_blur
            self.scaler = MinMaxScaler()
            im1 = self.scaler.fit_transform(im1)

            h_writef[i] = im1

        # if self.verbose:
        #     print(f'path to file: {combined}')

        h.close()

    def write_windows(self,name='',
                      windows_group = '',
                      dset_name = '',
                      logset_name = '',
                      target_size=128,
                      filter_threshold=5,
                      overwrite = False,
                      window_parms={  'fft_mode': 'abs',
                                        'interpol_factor': 2,
                                        'mode': 'fft',
                                        'window_size_x': 128,
                                        'window_size_y': 128,
                                        'window_step_x': 32,
                                        'window_step_y': 32,
                                        'zoom_factor': 2 }
                  ):
        """Generate and take tiled windows with applied parameters. 
        Writes a raw version and version with logarithm and thresholding applied to h5 file

        Args:
            name (str): name of sample (ex 'Annealed','Oxygen')
            window_params (dict, optional): parameters to give pycroscopy windowing function. Defaults to {}.
            windows_group (str, optional): name of the h5 group where window datasets are written. Defaults to 'windows'.
            dset_name (str, optional): name of the raw h5 dataset. Defaults to 'windows_data'.
            logset_name (str, optional): name of the log+threshold h5 dataset. Defaults to 'windows_logdata'.
            target_size (int, optional): how many pixels are in the final log dataset. Defaults to 128.
            filter_threshold (int, optional): cutoff for log dataset. Defaults to 5.
            overwrite (bool): whether or not to delete existing window file
            window_params (dict):

        Returns:
        returns ImageWindowing object. From pycroscopy.image package
        """     
        window_parms['interpol_factor'] = target_size/window_parms['window_size_x']*window_parms['zoom_factor']
        iw = ImageWindowing(window_parms)
        h = self.open_combined_h5(name)

        windows_group+='windows'
        dset_name+='windows_data'
        logset_name+='windows_logdata'
        

        # set windows group
        if windows_group not in h.keys(): 
            h_windows=h.create_group(windows_group)
        h_windows=h[windows_group]
        
        for i,img_path in enumerate(tqdm(self.list_imgs())):
            tic = time.perf_counter()
            im_dataset = sidpy.Dataset.from_array( 
                h['All_filtered'][i]
                    )
            windows = iw.MakeWindows(im_dataset)

            if f'filler' in h[windows_group]: del h[windows_group][f'filler']
            filler = h[windows_group].create_group(f'filler')

            pyNSID.hdf_io.write_nsid_dataset(windows, filler, main_data_name="windows");
            a,b,x,y = h[windows_group]['filler']['windows']['windows'].shape
            data = h[windows_group]['filler']['windows']['windows'][:].reshape(-1,x,y)

            if overwrite: 
                if dset_name in h[windows_group].keys(): del h[windows_group][dset_name]
                d_windows=h[windows_group].create_dataset(dset_name,shape=(self.t_len*a*b,x,y))
                if logset_name in h[windows_group].keys(): del h[windows_group][logset_name]
                logdata= h[windows_group].create_dataset(logset_name,
                                                        shape=(self.t_len*a*b,1,target_size,target_size),
                                                        dtype='f4')
            
            # toc = time.perf_counter()
            # print(tic-toc)

            else:
                if dset_name not in h[windows_group].keys(): 
                    d_windows=h[windows_group].create_dataset(dset_name,shape=(self.t_len*a*b,x,y))
                if logset_name not in h[windows_group].keys(): 
                    logdata= h[windows_group].create_dataset(logset_name,
                                                            shape=(self.t_len*a*b,1,target_size,target_size),
                                                            dtype='f4')            
            d_windows=h[windows_group][dset_name]
            logdata=h[windows_group][logset_name]
            
            d_windows[i*a*b:(i+1)*a*b] = data
            data = data.reshape(-1,1,x,y)
            # data = skimage.transform.resize(data,(a*b,1,target_size,target_size))
            data = np.log(data+1)
            data[data>filter_threshold]=filter_threshold
            logdata[i*a*b:(i+1)*a*b] = data

        if self.verbose: # print shape and 
            print('shape: ',a,b,target_size,target_size)
            pprint(window_parms)

        d_windows.attrs['orig_shape'] = (self.t_len,a,b,x,y)
        logdata.attrs['orig_shape'] = (self.t_len,a,b,target_size,target_size)
        logdata.attrs['filter_threshold'] = filter_threshold
        for key,val in window_parms.items(): # write metadata
            d_windows.attrs[key]=val
            logdata.attrs[key]=val

        h.close()

        return iw


# class Bright_Field_Dataset:
#     """Class for the STEM dataset.
#     """

#     def __init__(self, data_path):
#         """Initialization of the class.

#         Args:
#             data_path (string): path where the hyperspy file is located
#         """

#     self.data_path = data_path


    # @property
    # def log_data(self):
    #     return self._log_data

    # @log_data.setter
    # def log_data(self, log_data):
    #     # add 1 to avoid log(0)
    #     self._log_data = np.log(log_data.data + 1)
