#!/usr/bin/env python3

import argparse
import asyncio
import atexit
import importlib
import os
import logging

from PyQt6 import QtCore, QtGui, QtWidgets
from qasync import QEventLoop

from sipyco.pc_rpc import AsyncioClient, Client
from sipyco.broadcast import Receiver
from sipyco import common_args
from sipyco.asyncio_tools import atexit_register_coroutine
from sipyco.sync_struct import Subscriber

from artiq import __artiq_dir__ as artiq_dir, __version__ as artiq_version
from artiq.tools import get_user_config_dir
from artiq.gui.models import ModelSubscriber
from artiq.gui import state, log
from artiq.dashboard import (experiments, shortcuts, explorer,
                             moninj, datasets, schedule, applets_ccb,
                             waveform, interactive_args)


def get_argparser():
    parser = argparse.ArgumentParser(description="ARTIQ Dashboard")
    parser.add_argument("--version", action="version",
                        version="ARTIQ v{}".format(artiq_version),
                        help="print the ARTIQ version number")
    parser.add_argument(
        "-s", "--server", default="::1",
        help="hostname or IP of the master to connect to (default: %(default)s)")
    parser.add_argument(
        "--port-notify", default=3250, type=int,
        help="TCP port to connect to for notifications (default: %(default)s)")
    parser.add_argument(
        "--port-control", default=3251, type=int,
        help="TCP port to connect to for control (default: %(default)s)")
    parser.add_argument(
        "--port-broadcast", default=1067, type=int,
        help="TCP port to connect to for broadcasts (default: %(default)s)")
    parser.add_argument(
        "--db-file", default=None,
        help="database file for local GUI settings (default: %(default)s)")
    parser.add_argument(
        "-p", "--load-plugin", dest="plugin_modules", action="append",
        help="Python module to load on startup")
    parser.add_argument(
        "--analyzer-proxy-timeout", default=5, type=float,
        help="connection timeout to core analyzer proxy (default: %(default)s)")
    parser.add_argument(
        "--analyzer-proxy-timer", default=5, type=float,
        help="retry timer to core analyzer proxy (default: %(default)s)")
    parser.add_argument(
        "--analyzer-proxy-timer-backoff", default=1.1, type=float,
        help="retry timer backoff multiplier to core analyzer proxy, (default: %(default)s)")
    common_args.verbosity_args(parser)
    return parser


class EditableTabBar(QtWidgets.QTabBar):
    def mouseDoubleClickEvent(self, event):
        index = self.tabAt(event.pos())
        if index != -1:
            current_name = self.tabText(index)
            new_name, ok = QtWidgets.QInputDialog.getText(
                self, "Rename Workspace", "Enter a new name:",
                text=current_name
            )
            if ok and new_name.strip():
                new_name = new_name.strip()
                self.setTabText(index, new_name)
                tab_widget = self.parent()
                if isinstance(tab_widget, QtWidgets.QTabWidget):
                    mdi_area = tab_widget.widget(index)
                    mdi_area.tab_name = new_name
        super().mouseDoubleClickEvent(event)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, server):
        QtWidgets.QMainWindow.__init__(self)

        icon = QtGui.QIcon(os.path.join(artiq_dir, "gui", "logo.svg"))
        self.setWindowIcon(icon)
        self.setWindowTitle("ARTIQ Dashboard - {}".format(server))

        qfm = QtGui.QFontMetrics(self.font())
        self.resize(140 * qfm.averageCharWidth(), 38 * qfm.lineSpacing())

        self.exit_request = asyncio.Event()

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setTabBar(EditableTabBar())
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_mdi_area)
        self.setCentralWidget(self.tab_widget)
        toolbar = QtWidgets.QToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")
        self.addToolBar(toolbar)

        add_area_action = QtWidgets.QAction("New Workspace", self)
        add_area_action.triggered.connect(self.new_mdi_area)
        toolbar.addAction(add_area_action)

    def add_mdi_area(self, title):
        """Create a new MDI area (tab) with the given title."""
        mdi_area = MdiArea()
        mdi_area.tab_name = title  # store the name for later lookup
        self.tab_widget.addTab(mdi_area, title)

    def new_mdi_area(self):
        """Add a new MDI area (tab) with an auto-generated title."""
        count = self.tab_widget.count() + 1
        title = f"Workspace {count}"
        self.add_mdi_area(title)
        self.tab_widget.setCurrentIndex(self.tab_widget.count() - 1)

    def close_mdi_area(self, index):
        """Handle closing an MDI area (tab)."""
        if self.tab_widget.count() == 1:
            logging.warning("Cannot close last workspace")
            return
        mdi_area = self.tab_widget.widget(index)
        for experiment in mdi_area.subWindowList():
            mdi_area.removeSubWindow(experiment)
            experiment.close()
        self.tab_widget.removeTab(index)
        mdi_area.deleteLater()

    def closeEvent(self, event):
        event.ignore()
        self.exit_request.set()

    def save_state(self):
        """
        Save MainWindow state including MDI areas.
        (This is separate from the QMainWindow state.)
        """
        mdi_areas = [self.tab_widget.tabText(i) for i in range(self.tab_widget.count())]
        return {
            "state": bytes(self.saveState()),
            "geometry": bytes(self.saveGeometry()),
            "mdi_areas": mdi_areas,
        }

    def restore_state(self, state):
        """Restore MainWindow state including MDI areas."""
        self.restoreGeometry(QtCore.QByteArray(state["geometry"]))
        self.restoreState(QtCore.QByteArray(state["state"]))
        for title in state.get("mdi_areas", []):
            self.add_mdi_area(title)

    def get_mdi_area_by_name(self, name):
        """
        Given a name (i.e. tab title), return the corresponding MDI area.
        Returns None if not found.
        """
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == name:
                return self.tab_widget.widget(i)
        return None


class MdiArea(QtWidgets.QMdiArea):
    def __init__(self):
        QtWidgets.QMdiArea.__init__(self)
        self.pixmap = QtGui.QPixmap(os.path.join(
            artiq_dir, "gui", "logo_ver.svg"))

        self.setActivationOrder(
            QtWidgets.QMdiArea.WindowOrder.ActivationHistoryOrder)

        self.tile = QtGui.QShortcut(
            QtGui.QKeySequence('Ctrl+Shift+T'), self)
        self.tile.activated.connect(
            lambda: self.tileSubWindows())

        self.cascade = QtGui.QShortcut(
            QtGui.QKeySequence('Ctrl+Shift+C'), self)
        self.cascade.activated.connect(
            lambda: self.cascadeSubWindows())
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

    def paintEvent(self, event):
        QtWidgets.QMdiArea.paintEvent(self, event)
        painter = QtGui.QPainter(self.viewport())
        x = (self.width() - self.pixmap.width()) // 2
        y = (self.height() - self.pixmap.height()) // 2
        painter.setOpacity(0.5)
        painter.drawPixmap(x, y, self.pixmap)

def main():
    # initialize application
    args = get_argparser().parse_args()
    widget_log_handler = log.init_log(args, "dashboard")

    # load any plugin modules first (to register argument_ui classes, etc.)
    if args.plugin_modules:
        for mod in args.plugin_modules:
            importlib.import_module(mod)

    if args.db_file is None:
        args.db_file = os.path.join(get_user_config_dir(),
                                    "artiq_dashboard_{server}_{port}.pyon".format(
                                    server=args.server.replace(":", "."),
                                    port=args.port_notify))

    forced_platform = []
    if (QtGui.QGuiApplication.platformName() == "wayland" and
            not os.getenv("QT_QPA_PLATFORM")):
        # force XCB instead of Wayland due to applets not embedding
        forced_platform = ["-platform", "xcb"]
    app = QtWidgets.QApplication(["ARTIQ Dashboard"] + forced_platform)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    atexit.register(loop.close)
    smgr = state.StateManager(args.db_file)

    # create connections to master
    rpc_clients = dict()
    for target in "schedule", "experiment_db", "dataset_db", "device_db", "interactive_arg_db":
        client = AsyncioClient()
        loop.run_until_complete(client.connect_rpc(
            args.server, args.port_control, target))
        atexit.register(client.close_rpc)
        rpc_clients[target] = client

    master_management = Client(args.server, args.port_control, "master_management")
    try:
        server_name = master_management.get_name()
    finally:
        master_management.close_rpc()

    disconnect_reported = False

    def report_disconnect():
        nonlocal disconnect_reported
        if not disconnect_reported:
            logging.error("connection to master lost, "
                          "restart dashboard to reconnect")
        disconnect_reported = True

    sub_clients = dict()
    for notifier_name, modelf in (("explist", explorer.Model),
                                  ("explist_status", explorer.StatusUpdater),
                                  ("datasets", datasets.Model),
                                  ("schedule", schedule.Model),
                                  ("interactive_args", interactive_args.Model)):
        subscriber = ModelSubscriber(notifier_name, modelf, report_disconnect)
        loop.run_until_complete(subscriber.connect(
            args.server, args.port_notify))
        atexit_register_coroutine(subscriber.close, loop=loop)
        sub_clients[notifier_name] = subscriber

    broadcast_clients = dict()
    for target in "log", "ccb":
        client = Receiver(target, [], report_disconnect)
        loop.run_until_complete(client.connect(
            args.server, args.port_broadcast))
        atexit_register_coroutine(client.close, loop=loop)
        broadcast_clients[target] = client

    # initialize main window
    main_window = MainWindow(args.server if server_name is None else server_name)

    # create UI components
    expmgr = experiments.ExperimentManager(main_window,
                                           sub_clients["datasets"],
                                           sub_clients["explist"],
                                           sub_clients["schedule"],
                                           rpc_clients["schedule"],
                                           rpc_clients["experiment_db"])
    smgr.register(expmgr)
    smgr.register(main_window)
    d_shortcuts = shortcuts.ShortcutsDock(main_window, expmgr)
    smgr.register(d_shortcuts)
    d_explorer = explorer.ExplorerDock(expmgr, d_shortcuts,
                                       sub_clients["explist"],
                                       sub_clients["explist_status"],
                                       rpc_clients["schedule"],
                                       rpc_clients["experiment_db"],
                                       rpc_clients["device_db"])
    smgr.register(d_explorer)

    d_datasets = datasets.DatasetsDock(sub_clients["datasets"],
                                       rpc_clients["dataset_db"])
    smgr.register(d_datasets)

    d_applets = applets_ccb.AppletsCCBDock(main_window,
                                           sub_clients["datasets"],
                                           rpc_clients["dataset_db"],
                                           expmgr,
                                           extra_substitutes={
                                               "server": args.server,
                                               "port_notify": args.port_notify,
                                               "port_control": args.port_control,
                                           },
                                           loop=loop)
    atexit_register_coroutine(d_applets.stop, loop=loop)
    smgr.register(d_applets)
    broadcast_clients["ccb"].notify_cbs.append(d_applets.ccb_notify)

    d_ttl_dds = moninj.MonInj(rpc_clients["schedule"], main_window)
    smgr.register(d_ttl_dds)
    atexit_register_coroutine(d_ttl_dds.stop, loop=loop)

    d_waveform = waveform.WaveformDock(
        args.analyzer_proxy_timeout,
        args.analyzer_proxy_timer,
        args.analyzer_proxy_timer_backoff
    )
    atexit_register_coroutine(d_waveform.stop, loop=loop)

    d_interactive_args = interactive_args.InteractiveArgsDock(
        sub_clients["interactive_args"],
        rpc_clients["interactive_arg_db"]
    )

    d_schedule = schedule.ScheduleDock(
        rpc_clients["schedule"], sub_clients["schedule"])
    smgr.register(d_schedule)

    logmgr = log.LogDockManager(main_window)
    smgr.register(logmgr)
    broadcast_clients["log"].notify_cbs.append(logmgr.append_message)
    widget_log_handler.callback = logmgr.append_message

    # lay out docks
    right_docks = [
        d_explorer, d_shortcuts,
        d_datasets, d_applets,
        d_waveform, d_interactive_args
    ]
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, right_docks[0])
    for d1, d2 in zip(right_docks, right_docks[1:]):
        main_window.tabifyDockWidget(d1, d2)
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, d_schedule)

    # load/initialize state
    if os.name == "nt":
        # HACK: show the main window before creating applets.
        # Otherwise, the windows of those applets that are in detached
        # QDockWidgets fail to be embedded.
        main_window.show()
    smgr.load()

    def init_cbs(ddb):
        d_ttl_dds.dm.init_ddb(ddb)
        d_waveform.init_ddb(ddb)
        return ddb
    devices_sub = Subscriber("devices", init_cbs, [d_ttl_dds.dm.notify_ddb, d_waveform.notify_ddb])
    loop.run_until_complete(devices_sub.connect(args.server, args.port_notify))
    atexit_register_coroutine(devices_sub.close, loop=loop)

    smgr.start(loop=loop)
    atexit_register_coroutine(smgr.stop, loop=loop)

    # create first log dock if not already in state
    d_log0 = logmgr.first_log_dock()
    if d_log0 is not None:
        main_window.tabifyDockWidget(d_schedule, d_log0)
    d_moninj0 = d_ttl_dds.first_moninj_dock()
    if d_moninj0 is not None:
        main_window.tabifyDockWidget(right_docks[-1], d_moninj0)

    if server_name is not None:
        server_description = server_name + " ({})".format(args.server)
    else:
        server_description = args.server
    logging.info("ARTIQ dashboard %s connected to master %s",
                 artiq_version, server_description)
    # run
    main_window.show()
    loop.run_until_complete(main_window.exit_request.wait())


if __name__ == "__main__":
    main()
