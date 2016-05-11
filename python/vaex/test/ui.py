__author__ = 'maartenbreddels'
import unittest
import os
import tempfile
import logging
import numpy as np
import PIL.Image
import PIL.ImageChops

import vaex as vx
import vaex.ui
import vaex.ui.main
import vaex.ui.layers
import vaex.utils
import vaex.dataset
import vaex.execution
import vaex.webserver
from vaex.ui.qt import QtGui, QtCore, QtTest

import vaex.ui.qt as dialogs

# this will trigger more code, such as the canceling in between computation
vaex.execution.buffer_size = 10000
#vx.set_log_level_off()

example_path = vaex.utils.get_data_file("helmi-dezeeuw-2000-10p.hdf5")
vaex.ui.hidden = True

qt_app = QtGui.QApplication([])

base_path = os.path.dirname(__file__)
def get_comparison_image(name):
	return os.path.join(base_path, "images", name+".png")

#logging.getLogger("vaex.ui.queue").setLevel(logging.DEBUG)
#logging.getLogger("vaex.ui").setLevel(logging.DEBUG)
vx.set_log_level_warning()
vx.set_log_level_debug()
import logging
logger = logging.getLogger("vaex.test.ui")


overwrite_images = False

class CallCounter(object):
	def __init__(self, return_value=None):
		self.counter = 0
		self.return_value = return_value

	def __call__(self, *args, **kwargs):
		self.counter += 1
		return self.return_value

class TestMain(unittest.TestCase):
	def setUp(self):
		self.dataset = vaex.dataset.DatasetArrays("dataset")

		self.x = x = np.arange(10)
		self.y = y = x ** 2
		self.dataset.add_column("x", x)
		self.dataset.add_column("y", y)
		self.dataset.set_variable("t", 1.)
		self.dataset.add_virtual_column("z", "x+t*y")

		self.app = vx.ui.main.VaexApp()

	def test_default(self):
		app = vx.ui.main.VaexApp(open_default=False)
		self.assert_(app.dataset_selector.is_empty())
		self.assertEqual(None, app.current_dataset)

		app = vx.ui.main.VaexApp(open_default=True)
		self.assert_(not app.dataset_selector.is_empty())
		self.assertIsNotNone(app.current_dataset)

	def test_add_dataset(self):
		app = vx.ui.main.VaexApp()
		ds = vx.example()
		app.dataset_selector.add(ds)
		self.assert_(not app.dataset_selector.is_empty())
		self.assertEqual(int(app.dataset_panel.label_length.text().replace(",", "")), len(ds))
		self.assertEqual(ds, app.current_dataset)

	def test_open_dataset(self):
		app = vx.ui.main.VaexApp()
		ds = app.dataset_selector.open(example_path)
		self.assert_(not app.dataset_selector.is_empty())
		self.assertEqual(int(app.dataset_panel.label_length.text().replace(",", "")), len(ds))
		self.assertEqual(ds, app.current_dataset)

	def test_export(self):
		path_hdf5 = tempfile.mktemp(".hdf5")
		path_hdf5_ui = tempfile.mktemp(".hdf5")
		path_fits = tempfile.mktemp(".fits")
		path_fits_ui = tempfile.mktemp(".fits")

		for dataset in [self.dataset]:
			self.app.dataset_selector.add(dataset)
			for fraction in [1, 0.5]:
				dataset.set_active_fraction(fraction)
				dataset.select("x > 3")
				length = len(dataset)
				# TODO: gui doesn't export virtual columns, add "z" to this list
				for column_names in [["x", "y"], ["x"], ["y"]]:
					for byteorder in "=<>":
						for shuffle in [False, True]:
							for selection in [False, True]:
								for export in [dataset.export_fits, dataset.export_hdf5] if byteorder == ">" else [dataset.export_hdf5]:
									type = "hdf5" if export == dataset.export_hdf5 else "fits"
									if shuffle and selection:
										continue # TODO: export should fail on this combination
									#print column_names, byteorder, shuffle, selection, type
									if export == dataset.export_hdf5:
										path = path_hdf5
										path_ui = path_hdf5_ui
										export(path, column_names=column_names, byteorder=byteorder, shuffle=shuffle, selection=selection)
									else:
										path = path_fits
										path_ui = path_fits_ui
										export(path, column_names=column_names, shuffle=shuffle, selection=selection)
									compare_direct = vx.open(path)

									dialogs.set_choose(1 if selection else 0).then("=<>".index(byteorder))
									# select columns
									dialogs.set_select_many(True, [name in column_names for name in dataset.get_column_names()])
									counter_confirm = CallCounter(return_value=shuffle)
									counter_info = CallCounter()
									dialogs.dialog_confirm = counter_confirm
									dialogs.dialog_info = counter_info
									dialogs.get_path_save = lambda *args: path_ui
									dialogs.ProgressExecution = dialogs.FakeProgressExecution
									import sys
									sys.stdout.flush()

									self.app.export(type=type)
									compare_ui = vx.open(path_ui)

									column_names = column_names or ["x", "y", "z"]
									self.assertEqual(compare_direct.get_column_names(), compare_ui.get_column_names())
									for column_name in column_names:
										values_ui = compare_ui.evaluate(column_name)
										values = compare_direct.evaluate(column_name)
										self.assertEqual(sorted(values), sorted(values_ui))


class TestPlotPanel(unittest.TestCase):
	def setUp(self):
		self.app = vx.ui.main.VaexApp([], open_default=True)

	def test_open_and_close(self):
		button = self.app.dataset_panel.button_2d
		self.app.show()
		self.app.hide()
		self.assert_(len(self.app.windows) == 0)
		QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
		self.assertEqual(len(self.app.windows), 1)
		self.assertEqual(self.app.windows[0], self.app.current_window)
		self.assertEqual(self.app.windows[0].dataset, self.app.current_dataset)

		self.app.current_window.close()
		self.assert_(len(self.app.windows) == 0)
		self.assertEqual(None, self.app.current_window)

from vaex.ui.plot_windows import PlotDialog

class TestPlotPanel(unittest.TestCase):
	def create_app(self):
		self.app = vx.ui.main.VaexApp([], open_default=True)
	def setUp(self):
		self.create_app()
		self.app.show()
		self.app.hide()
		self.open_window()
		self.window = self.app.current_window
		#self.window.xlabel = ""
		#self.window.ylabel = ""
		self.window.set_plot_size(512, 512)
		self.window.show()
		self.window.hide()
		self.layer = self.window.current_layer
		self.layer.state.colorbar = False
		self.no_exceptions = True
		import sys
		def testExceptionHook(type, value, tback):
			self.no_exceptions = False
			sys.__excepthook__(type, value, tback)

		sys.excepthook = testExceptionHook

		self.no_error_in_field = True
		def error_in_field(*args):
			print(args)
			self.no_error_in_field = False
			previous_error_in_field(*args)
		previous_error_in_field = vaex.ui.layers.LayerTable.error_in_field
		vaex.ui.layers.LayerTable.error_in_field = error_in_field
		def log_error(*args):
			print("dialog error", args)
		dialogs.dialog_error = log_error

	def tearDown(self):
		for dataset in self.app.dataset_selector.datasets:
			dataset.close_files()
		self.window.close()
		self.assertTrue(self.no_exceptions)
		self.assertTrue(self.no_error_in_field)

	def compare(self, fn1, fn2):
		assert os.path.exists(fn2), "image missing: cp {im1} {im2}".format(im1=fn1, im2=fn2)

		try:
			image1 = PIL.Image.open(fn1)
			image2 = PIL.Image.open(fn2)
			diff = PIL.ImageChops.difference(image1, image2)
			extrema = diff.getextrema()
			for i, (vmin, vmax) in enumerate(extrema):
				msg = "difference found between {im1} and {im2} in band {band}\n $ cp {im1} {im2}".format(im1=fn1, im2=fn2, band=i)
				if vmin != vmax and overwrite_images:
					image1.show()
					image2.show()
					done = False
					while not done:
						answer = raw_input("is the new image ok? [y/N]").lower().strip()
						if answer == "n":
							self.assertEqual(vmin, 0, msg)
							return
						if answer == "y":
							import shutil
							shutil.copy(fn1, fn2)
							return
				self.assertEqual(vmin, 0, msg)
				self.assertEqual(vmax, 0, msg)
		finally:
			image1.close()
			image2.close()


class TestPlotPanel1d(TestPlotPanel):
	def open_window(self):
		button = self.app.dataset_panel.button_histogram
		self.assert_(len(self.app.windows) == 0)
		QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)

	def test_x(self):
		QtTest.QTest.qWait(self.window.queue_update.default_delay)
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_x"))

	def test_r(self):
		self.layer.x = "sqrt(x**2+y**2)"
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_r"))

class TestPlotPanel2d(TestPlotPanel):
	"""
	:type window: PlotDialog
	"""
	def open_window(self):
		button = self.app.dataset_panel.button_2d
		self.assert_(len(self.app.windows) == 0)
		QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)


	def test_xy(self):
		QtTest.QTest.qWait(self.window.queue_update.default_delay)
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy"))

	def test_xr(self):
		self.layer.y = "sqrt(x**2+y**2)"
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xr"))

	def test_xy_weight_r(self):
		self.layer.weight = "sqrt(x**2+y**2)"
		self.layer.amplitude = "clip(average, 0, 40)"
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_weight_r"))

	def test_xy_vxvy(self):
		self.layer.vx = "vx"
		self.layer.vy = "vy"
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_vxvy"))

		counter = self.window.queue_update.counter
		# the following actions should not cause an update
		self.layer.vx = "vx"
		self.layer.vy = "vy"
		self.assertEqual(counter, self.window.queue_update.counter)
		self.layer.vx = ""
		self.assertEqual(counter, self.window.queue_update.counter)
		self.layer.vx = None
		self.assertEqual(counter, self.window.queue_update.counter)
		self.layer.vx = ""
		self.assertEqual(counter, self.window.queue_update.counter)
		# this should update it
		self.layer.vx = "vx"
		self.assertEqual(counter+1, self.window.queue_update.counter)
		self.window._wait()

	def test_xy_vxvy_as_option(self):
		self.window.remove_layer()
		self.window.add_layer(["x", "y"], vx="vx", vy="vy", colorbar="False")
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_vxvy"))

	def test_select_by_expression(self):
		self.window.xlabel = "x"
		self.window.ylabel = "y"
		##self.window._wait() # TODO: is this a bug? if we don't wait and directly do the selection, the ThreadPoolIndex
		## is entered twice, not sure this can happen from the gui
		vaex.ui.qt.set_choose("x < 0", True)
		logger.debug("click mouse")
		QtTest.QTest.mouseClick(self.layer.button_selection_expression, QtCore.Qt.LeftButton)
		logger.debug("clicked mouse")
		return
		self.window._wait()
		self.assertTrue(self.no_exceptions)

		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_selection_on_x"))

	def test_select_by_lasso(self):
		self.window._wait() # TODO: is this a bug? same as above
		vaex.ui.qt.set_choose("x < 0", True)
		x = [-10, 10, 10, -10]
		y = [-10, -10, 10, 10]
		self.layer.dataset.select_lasso("x", "y", x, y)
		#QtTest.QTest.mouseClick(self.layer.button_selection_expression, QtCore.Qt.LeftButton)
		self.assertLess(self.layer.dataset.selected_length(), len(self.layer.dataset))
		self.window._wait()
		self.assertTrue(self.no_exceptions)

	def test_layers(self):
		self.window.add_layer(["x", "z"])
		self.window._wait()

	def test_resolution(self):
		if 0: # keyClick doesn't work on osx it seems
			self.window.show()
			QtTest.QTest.qWaitForWindowShown(self.window)
			QtTest.QTest.keyClick(self.window, QtCore.Qt.Key_1, QtCore.Qt.ControlModifier|QtCore.Qt.AltModifier) # "Ctrl+Alt+1"should be 32x32
		else:
			self.window.action_resolution_list[0].trigger()
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_32x32"))

	def test_resolution_vector(self):
		self.layer.vx = "vx"
		self.layer.vy = "vy"
		self.window.action_resolution_vector_list[2].trigger()
		self.window._wait()
		filename = self.window.plot_to_png()
		self.compare(filename, get_comparison_image("example_xy_vxvy_32x32"))


	def test_invalid_expression(self):
		self.window._wait()

		with dialogs.assertError(2):
			self.layer.x = "vx*"
			self.layer.y = "vy&"
		with dialogs.assertError(3):
			self.layer.x = "hoeba(vx)"
			self.layer.x = "x(vx)"
			self.layer.y = "doesnotexist"
		with dialogs.assertError(2):
			self.layer.vx = "hoeba(vx)"
			self.layer.vy = "x(vx)"
		with dialogs.assertError(1):
			self.layer.weight = "hoeba(vx)"
		self.layer.x = "x"
		self.layer.y = "y"
		self.layer.weight = "z"
		#self.window._wait()
		# since this will be triggered, overrule it
		self.no_error_in_field = True

import sys
test_port = 29210 + sys.version_info[0] * 10 + sys.version_info[1]

class TestPlotPanel2dRemote(TestPlotPanel2d):
	use_websocket = True
	def create_app(self):
		global test_port
		self.app = vx.ui.main.VaexApp([], open_default=False)
		self.dataset_default = vaex.example()
		datasets = [self.dataset_default]
		self.webserver = vaex.webserver.WebServer(datasets=datasets, port=test_port)
		#print "serving"
		self.webserver.serve_threaded()
		#print "getting server object"
		scheme = "ws" if self.use_websocket else "http"
		self.server = vx.server("%s://localhost:%d" % (scheme, test_port), thread_mover=self.app.call_in_main_thread)
		datasets = self.server.datasets(as_dict=True)

		self.dataset = datasets[self.dataset_default.name]
		self.app.dataset_selector.add(self.dataset)
		test_port += 1

	def tearDown(self):
		#print "stop serving"
		TestPlotPanel2d.tearDown(self)
		self.webserver.stop_serving()

	def test_select_by_lasso(self):
		pass # TODO: cannot test since DatasetRemote.selected_length it not implemented

	def test_invalid_expression(self): pass
	#def test_resolution_vector(self): pass
	#def test_resolution(self): pass
	#def test_layers(self): pass
	def test_select_by_lasso(self): pass
	def test_select_by_expression(self): pass
	#def test_xy_vxvy_as_option(self): pass
	#def test_xy_vxvy(self): pass
	#def test_xy_weight_r(self): pass
	#def test_xr(self): pass
	#def test_xy(self): pass

if __name__ == '__main__':
    unittest.main()