import matplotlib.pyplot as plt
import math as m

def nic_plot2d(datas, pd, grid, xlabel, ylabel, title, axes, sub, size, leg_labels, ax):
    # Don't generate a new figure if it's being called from neh_subplot
    if sub != 1: fig, ax = plt.subplots(figsize=size)
    
    # Check that the datas length matches the plotting data length
    #for item in pd:
    #if len(datas) != len(pd): print('ERROR: The plotting information is not the same length as the datas to be plotted!')
    
    # Plot the appropriate type
    for i, data in enumerate(datas):
        if pd['type'] == 'normal':
            plt.plot(data[0],data[1], marker=pd['Mt'][i], markerfacecolor=pd['Mfc'][i], markeredgecolor=pd['Mec'][i], markeredgewidth=pd['Mew'][i], markersize=pd['Ms'][i], color=pd['Lc'][i], linewidth=pd['Lw'][i], linestyle=pd['Lt'][i])
        elif pd['type'] == 'semilogx':
            plt.semilogx(data[0],data[1], marker=pd['Mt'][i], markerfacecolor=pd['Mfc'][i], markeredgecolor=pd['Mec'][i], markeredgewidth=pd['Mew'][i], markersize=pd['Ms'][i], color=pd['Lc'][i], linewidth=pd['Lw'][i], linestyle=pd['Lt'][i])
        elif pd['type'] == 'semilogy':
            plt.semilogy(data[0],data[1], marker=pd['Mt'][i], markerfacecolor=pd['Mfc'][i], markeredgecolor=pd['Mec'][i], markeredgewidth=pd['Mew'][i], markersize=pd['Ms'][i], color=pd['Lc'][i], linewidth=pd['Lw'][i], linestyle=pd['Lt'][i])
        
    if grid != 0: ax.grid()
    
    if axes != 'auto': plt.axis(axes)

    nic_standard_axes(ax, xlabel, ylabel, leg_labels, title, sub)


def nic_standard_axes(ax, xlabel = '', ylabel = '', ylabelcolor='', title = '', leg_labels = None, sub=1):
    # STANDARDISED ASPECTS
    # Axis tick font
    plt.setp(ax.get_xticklabels(), rotation='horizontal', fontsize=10)
    plt.setp(ax.get_yticklabels(), rotation='horizontal', fontsize=10)

    # Axis labels
    if xlabel != '': ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
    if ylabel != '':
        if ylabelcolor:
            ax.set_ylabel(ylabel, fontsize=12, fontweight='bold', color=ylabelcolor)
        else:
            ax.set_ylabel(ylabel, fontsize=12, fontweight='bold')

    if ylabelcolor: ax.tick_params(axis='y', labelcolor=ylabelcolor)

    # Legend labels
    if leg_labels:
        if len(leg_labels) > 0: ax.legend(leg_labels)

    # Plot title (smaller if part of a subplot)
    plt.title(title, fontsize=14 if sub != 1 else 12, fontweight='bold')

    # Don't show the figure if it's being called from neh_subplot
    if sub != 1: plt.show()


def nic_subplot2d(plots, bigtitle, shape, size):
    # Check that the length of the plots data provided matches the number of subplots requested
    Nplots = len(plots)
    rows = m.floor(shape/10)
    cols = shape-10*m.floor(shape/10)
    if Nplots != rows*cols: print('ERROR: Subplot datas length doesn''t match requested subplots shape!')

    fig = plt.figure(figsize=size)
    for i in range(1,Nplots+1):
        ax = fig.add_subplot(shape*10+i)
        # Turn off redundant x-ticks
        if i < (rows-1)*cols:
            ax.tick_params(labelbottom=False) 
        
        # Turn off redundant y-ticks
        if i%cols != 1:
            ax.tick_params(labelleft=False) 

        nic_plot2d(plots[i-1]['datas'],plots[i-1]['pd'],plots[i-1]['grid'],plots[i-1]['xlabel'],plots[i-1]['ylabel'],plots[i-1]['title'],plots[i-1]['axes'],1,[1,1],plots[i-1]['leg_labels'],ax)
    
    plt.suptitle(bigtitle, fontsize=14,fontweight='bold')
    plt.show()

    
def neh_contourplot(dictionary, X_key, Y_key, Z_key, color_lims, color_map, xlabel='xlabel', ylabel='ylabel', title='title', size=[10, 7], sub=0):
    # Don't generate a new figure if it's being called from neh_subplot
    if sub != 1: fig, ax = plt.subplots(figsize=size)
    #     fig = plt.figure()
    #     ax = fig.add_subplot(111)

    X, Y = plt.meshgrid(dictionary[X_key], dictionary[Y_key])
    # Check that the vector lengths conform to the plot matrix, and if not try to reverse the transpose
    Z = dictionary[Z_key]
    if Z.shape != X.shape:
        Z = plt.transpose(Z)
    # pdb.set_trace()
    plt.pcolor(X, Y, Z, vmin=color_lims[0], vmax=color_lims[1], cmap=color_map, norm=MidpointNormalize(midpoint=0))
    cbar = plt.colorbar()
    cbar.ax.tick_params(labelsize=14)

    # Axis tick font (rotate the x ticks if they are dates - too long to be horizontal)
    plt.setp(ax.get_xticklabels(), rotation='horizontal', fontsize=10)
    plt.setp(ax.get_yticklabels(), rotation='horizontal', fontsize=10)

    # Axis labels
    if xlabel != '': plt.xlabel(xlabel, fontsize=12, fontweight='bold')
    if ylabel != '': plt.ylabel(ylabel, fontsize=12, fontweight='bold')

    # Plot title (smaller if part of a subplot)
    plt.title(title, fontsize=14 if sub != 1 else 12, fontweight='bold')

    # Don't show the figure if it's being called from neh_subplot
    if sub != 1: plt.show()


# class MidpointNormalize(colors.Normalize):
#     def __init__(self, vmin=None, vmax=None, midpoint=None, clip=False):
#         self.midpoint = midpoint
#         colors.Normalize.__init__(self, vmin, vmax, clip)
#
#     def __call__(self, value, clip=None):
#         # I'm ignoring masked values and all kinds of edge cases to make a
#         # simple example...
#         x, y = [self.vmin, self.midpoint, self.vmax], [0, 0.5, 1]
#         return nplt.ma.masked_array(nplt.interp(value, x, y))