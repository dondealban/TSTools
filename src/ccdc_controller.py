# -*- coding: utf-8 -*
# vim: set expandtab:ts=4
"""
/***************************************************************************
 CCDCToolsDialog
                                 A QGIS plugin
 Plotting & visualization tools for CCDC Landsat time series analysis
                             -------------------
        begin                : 2013-03-15
        copyright            : (C) 2013 by Chris Holden
        email                : ceholden@bu.edu
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import QgsRasterLayer, QgsMapLayerRegistry

from functools import partial
import itertools

import numpy as np

from ccdc_timeseries import CCDCTimeSeries

class Controller(object):

    def __init__(self, control, plot, iface):
        """
        Controller stores options specified in control panel & makes them
        available for plotter by handling all signals...
        """
        self.ctrl = control
        self.plt = plot
        self.iface = iface
        
        ### Options
        self.opt = {}
        self.opt['plot'] = False
        self.opt['band'] = 0
        # TODO: turn these into specifics for each band
        self.opt['scale'] = True
        self.opt['scale_factor'] = 0.25
        self.opt['min'] = np.zeros(1, dtype=np.int)
        self.opt['max'] = np.ones(1, dtype=np.int) * 10000
        self.opt['fmask'] = True
        self.opt['fit'] = True
        self.opt['break'] = True
        self.opt['plotlayer'] = True
        self.opt['picker_tol'] = 2

    def get_time_series(self, location, image_pattern, stack_pattern):
        """
        Loads the time series class when called by ccdctools and feeds
        information to controls & plotter
        """
        self.ts = CCDCTimeSeries(location, image_pattern, stack_pattern)
        if self.ts:
            # Update plot & controls
            self.update_display()
            self.ctrl.update_table(self.ts, self.opt)
            self.add_signals()

    def update_display(self):
        """
        Once ts is read, update controls & plot with relevant information
        (i.e. update)
        """
        if self.opt['scale']:
            self.calculate_scale()
        self.ctrl.update_options(self.ts, self.opt)
        self.plt.update_plot(self.ts, self.opt)

    def add_signals(self):
        """
        Add the signals to the options tab
        """
        ### Raster band select checkbox
        self.ctrl.combox_band.currentIndexChanged.connect(partial(
            self.set_band_select))
        
        ### Plotting scale options
        # Auto scale
        self.ctrl.cbox_scale.stateChanged.connect(self.set_scale)
        # Manual set of min/max
        validator = QIntValidator(0, 10000, self.ctrl)
        self.ctrl.edit_min.returnPressed.connect(partial(
            self.set_min, self.ctrl.edit_min, validator))
        # Plot Y max
        self.ctrl.edit_max.returnPressed.connect(partial(
            self.set_max, self.ctrl.edit_max, validator))

        ### Time series options
        # Show or hide Fmask masked values
        self.ctrl.cbox_fmask.stateChanged.connect(self.set_fmask)
        # Show or hide fitted time series
        self.ctrl.cbox_ccdcfit.stateChanged.connect(self.set_fit)
        # Show or hide break points
        self.ctrl.cbox_ccdcbreak.stateChanged.connect(self.set_break)

        ### Add layer from time series plot points
        # Turn on default for checkbox
        self.ctrl.cbox_plotlayer.stateChanged.connect(self.set_plotlayer)
        # Connect/disconnect matplotlib event signal based on checkbox default
        self.set_plotlayer(self.ctrl.cbox_plotlayer.checkState())

        ### Image tab panel helpers for add/remove layers
        # NOTE: QGIS added "layersAdded" in 1.8(?) to replace some older
        #       signals. It looks like they intended on adding layersRemoved
        #       to replace layersWillBeRemoved/etc, but haven't gotten around
        #       to it... so we keep with the old signal for now
        #       http://www.qgis.org/api/classQgsMapLayerRegistry.html
        QgsMapLayerRegistry.instance().layersAdded.connect(
            self.map_layers_added)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(
            self.map_layers_removed)

        ### Image tab panel
        self.ctrl.image_table.itemClicked.connect(self.get_tablerow_clicked)

    def calculate_scale(self):
        """
        Automatically calculate the min/max for time series plotting
        """
        self.opt['min'] = [np.min(band) * (1 - self.opt['scale_factor']) 
                           for band in self.ts.data[:, ]]
        self.opt['max'] = [np.max(band) * (1 + self.opt['scale_factor'])
                           for band in self.ts.data[:, ]]

    ### Slots for options tab
    def set_band_select(self, index):
        """
        Update the band selected & replot
        """
        self.opt['band'] = index
        self.ctrl.update_options(self.ts, self.opt)
        self.plt.update_plot(self.ts, self.opt)

    def set_scale(self, state):
        """
        Automatically set the scale for each band & disable manual set
        """
        if state == Qt.Checked:
            self.opt['scale'] = True
        elif state == Qt.Unchecked:
            self.opt['scale'] = False
        self.ctrl.edit_min.setEnabled(not self.opt['scale'])
        self.ctrl.edit_max.setEnabled(not self.opt['scale'])

    def set_min(self, edit, validator):
        """
        If valid, update the minimum scale & replot
        """
        state, pos = validator.validate(edit.text(), 0)

        if state == QValidator.Acceptable:
            self.opt['min'][self.opt['band']] = int(edit.text())
        self.plt.update_plot(self.ts, self.opt)
    
    def set_max(self, edit, validator):
        """
        If valid, update the maximum scale & replot
        """
        state, pos = validator.validate(edit.text(), 0)

        if state == QValidator.Acceptable:
            self.opt['max'][self.opt['band']] = int(edit.text())
        self.plt.update_plot(self.ts, self.opt)

    def set_fmask(self, state):
        """
        Turn on or off the Fmask masking & replot
        """
        if state == Qt.Checked:
            self.opt['fmask'] = True
        elif state == Qt.Unchecked:
            self.opt['fmask'] = False
        # Update the data for without the masks
        self.ts.get_ts_pixel(self.ts.x, self.ts.y, self.opt['fmask'])
        self.plt.update_plot(self.ts, self.opt)

    def set_fit(self, state):
        """
        Turn on or off the CCDC fit lines & replot
        """
        if state == Qt.Checked:
            self.opt['fit'] = True
        elif state == Qt.Unchecked:
            self.opt['fit'] = False
        self.plt.update_plot(self.ts, self.opt)

    def set_break(self, state):
        """
        Turn on or off the CCDC break indicator & replot
        """
        if state == Qt.Checked:
            self.opt['break'] = True
        elif state == Qt.Unchecked:
            self.opt['break'] = False
        self.plt.update_plot(self.ts, self.opt)

    def set_plotlayer(self, state):
        """
        Turns on or off the adding of map layers for a data point on plot
        """
        if state == Qt.Checked:
            self.opt['plotlayer'] = True
            self.cid = self.plt.fig.canvas.mpl_connect('pick_event',
                                                       self.plot_add_layer)
        elif state == Qt.Unchecked:
            self.opt['plotlayer'] = False
            self.plt.fig.canvas.mpl_disconnect(self.cid)

    ### Slots for plot window
    def plot_add_layer(self, event):
        """
        Receives matplotlib event and adds layer for data point picked

        Reference:
            http://matplotlib.org/users/event_handling.html
        """
        line = event.artist
        index = event.ind

        print 'Number selected: %s' % str(len(index))
        if len(index) > 1:
            print 'Error, selected more than one item...'
            print 'Defaulting to the first'
            index = index[0]

        print 'Selected date %s' % str(line.get_xdata()[index])

        # Use the QgsMapLayerRegistery singleton to access/add/remove layers
        reg = QgsMapLayerRegistry.instance()
        # Check if added #TODO refactor this code out?
        added = [(self.ts.stacks[index] == layer.source(), layer)
                 for layer in reg.mapLayers().values()]
        # We haven't already added it
        if all(not add[0] for add in added) or len(added) == 0:
            print 'Adding new raster layer for plot point'
            rlayer = QgsRasterLayer(self.ts.stacks[index],
                                    self.ts.image_ids[index])
            if rlayer.isValid():
                reg.addMapLayer(rlayer)

    ### Function helper for MapTool slot
    def fetch_data(self, pos):
        """
        Receives QgsPoint, transforms into pixel coordinates, retrieves data
        and updates plot
        """
        print 'Pos: %s' % str(pos)
        px = int((pos[0] - self.ts.geo_transform[0]) / 
                 self.ts.geo_transform[1])
        py = int((pos[1] - self.ts.geo_transform[3]) / 
                 self.ts.geo_transform[5])
        self.ts.get_ts_pixel(px, py,
                             mask=self.opt['fmask'])
        self.ts.get_reccg_pixel(px, py)
        print 'Pixel x/y %s/%s' % (px, py)
        print 'nBreaks = %s' % len(self.ts.reccg)
        self.plt.update_plot(self.ts, self.opt)
    
    ### Image table slots
    def get_tablerow_clicked(self, item):
        """
        If user clicks checkbox for image in image table, will add/remove
        image layer from map layers.
        """
        print '%s,%s row,col triggered' % (str(item.row()), str(item.column()))
        if item.column() != 0:
            return

        # Use the QgsMapLayerRegistery singleton to access/add/remove layers
        reg = QgsMapLayerRegistry.instance()
        # Check if added
        added = [(self.ts.stacks[item.row()] == layer.source(), layer)
                 for layer in reg.mapLayers().values()]
        if item.checkState() == Qt.Checked:
            # If current layers do not include checked image, add
            if all(not add[0] for add in added) or len(added) == 0:
                rlayer = QgsRasterLayer(self.ts.stacks[item.row()],
                                        self.ts.image_ids[item.row()])
                if rlayer.isValid():
                    reg.addMapLayer(rlayer)
        elif item.checkState() == Qt.Unchecked:
            # If added is true and we now have unchecked, remove
            for (rm, layer) in added:
                if rm:
                    print 'Removing unchecked layer...'
                    reg.removeMapLayer(layer.id())

    def map_layers_added(self, layers):
        """
        Check if newly added layer is part of stacks; if so, make sure image
        checkbox is clicked in the images tab
        """
        print 'Added a map layer'
        for layer in layers:
            rows_added = [row for (row, stack) in enumerate(self.ts.stacks)
                          if layer.source() == stack]
            print 'Added these rows: %s' % str(rows_added)
            for row in rows_added:
                item = self.ctrl.image_table.item(row, 0)
                if item:
                    if item.checkState() == Qt.Unchecked:
                        item.setCheckState(Qt.Checked)

    def map_layers_removed(self, layer_ids):
        """
        Unchecks image tab checkbox for layers removed.
        
        Note that layers is a QStringList of layer IDs. A layer ID contains
        the layer name appended by the datetime added
        """
        print 'Removed a map layer'
        for layer_id in layer_ids:
            rows_removed = [row for row, (image_id, fname) in 
                enumerate(itertools.izip(self.ts.image_ids, self.ts.files))
                if image_id in layer_id or fname in layer_id]
            print 'Removed these rows %s' % str(rows_removed)
            for row in rows_removed:
                item = self.ctrl.image_table.item(row, 0)
                if item:
                    if item.checkState() == Qt.Checked:
                        item.setCheckState(Qt.Unchecked)

    def disconnect(self):
        """
        Disconnect all signals added to various components
        """
        print 'TODO'