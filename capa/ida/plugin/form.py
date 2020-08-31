# Copyright (C) 2020 FireEye, Inc. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
# You may obtain a copy of the License at: [package root]/LICENSE.txt
# Unless required by applicable law or agreed to in writing, software distributed under the License
#  is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and limitations under the License.

import os
import json
import collections

from PyQt5 import QtGui, QtCore, QtWidgets

import idaapi

import capa.main
import capa.rules
import capa.ida.helpers
import capa.render.utils as rutils
import capa.features.extractors.ida

from capa.ida.plugin.view import CapaExplorerQtreeView
from capa.ida.plugin.model import CapaExplorerDataModel
from capa.ida.plugin.proxy import CapaExplorerSortFilterProxyModel
from capa.ida.plugin.hooks import CapaExplorerIdaHooks


class CapaExplorerForm(idaapi.PluginForm):
    def __init__(self, name, logger):
        """ """
        super(CapaExplorerForm, self).__init__()

        self.form_title = name
        self.logger = logger

        self.rule_path = ""

        self.parent = None
        self.ida_hooks = None
        self.doc = None

        # models
        self.model_data = None
        self.model_proxy = None

        # user interface elements
        self.view_limit_results_by_function = None
        self.view_tree = None
        self.view_summary = None
        self.view_attack = None
        self.view_tabs = None
        self.view_menu_bar = None

    def OnCreate(self, form):
        """ """
        self.parent = self.FormToPyQtWidget(form)
        self.load_interface()
        self.load_capa_results()
        self.load_ida_hooks()

        self.view_tree.reset()

        self.logger.info("form created.")

    def Show(self):
        """ """
        self.logger.info("form show.")
        return idaapi.PluginForm.Show(
            self, self.form_title, options=(idaapi.PluginForm.WOPN_TAB | idaapi.PluginForm.WCLS_CLOSE_LATER)
        )

    def OnClose(self, form):
        """ form is closed """
        self.unload_ida_hooks()
        self.ida_reset()
        self.logger.info("form closed.")

    def load_interface(self):
        """ load user interface """
        # load models
        self.model_data = CapaExplorerDataModel()
        self.model_proxy = CapaExplorerSortFilterProxyModel()
        self.model_proxy.setSourceModel(self.model_data)

        # load tree
        self.view_tree = CapaExplorerQtreeView(self.model_proxy, self.parent)

        # load summary table
        self.load_view_summary()
        self.load_view_attack()

        # load parent tab and children tab views
        self.load_view_tabs()
        self.load_view_checkbox_limit_by()
        self.load_view_summary_tab()
        self.load_view_attack_tab()
        self.load_view_tree_tab()

        # load menu bar and sub menus
        self.load_view_menu_bar()
        self.load_file_menu()

        # load parent view
        self.load_view_parent()

    def load_view_tabs(self):
        """ load tabs """
        tabs = QtWidgets.QTabWidget()
        self.view_tabs = tabs

    def load_view_menu_bar(self):
        """ load menu bar """
        bar = QtWidgets.QMenuBar()
        self.view_menu_bar = bar

    def load_view_summary(self):
        """ load capa summary table """
        table_headers = [
            "Capability",
            "Namespace",
        ]

        table = QtWidgets.QTableWidget()

        table.setColumnCount(len(table_headers))
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setHorizontalHeaderLabels(table_headers)
        table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft)
        table.setShowGrid(False)
        table.setStyleSheet("QTableWidget::item { padding: 25px; }")

        self.view_summary = table

    def load_view_attack(self):
        """ load MITRE ATT&CK table """
        table_headers = [
            "ATT&CK Tactic",
            "ATT&CK Technique ",
        ]

        table = QtWidgets.QTableWidget()

        table.setColumnCount(len(table_headers))
        table.verticalHeader().setVisible(False)
        table.setSortingEnabled(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setHorizontalHeaderLabels(table_headers)
        table.horizontalHeader().setDefaultAlignment(QtCore.Qt.AlignLeft)
        table.setShowGrid(False)
        table.setStyleSheet("QTableWidget::item { padding: 25px; }")

        self.view_attack = table

    def load_view_checkbox_limit_by(self):
        """ load limit results by function checkbox """
        check = QtWidgets.QCheckBox("Limit results to current function")
        check.setChecked(False)
        check.stateChanged.connect(self.slot_checkbox_limit_by_changed)

        self.view_limit_results_by_function = check

    def load_view_parent(self):
        """ load view parent """
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(self.view_tabs)
        layout.setMenuBar(self.view_menu_bar)

        self.parent.setLayout(layout)

    def load_view_tree_tab(self):
        """ load capa tree tab view """
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.view_limit_results_by_function)
        layout.addWidget(self.view_tree)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.view_tabs.addTab(tab, "Tree View")

    def load_view_summary_tab(self):
        """ load capa summary tab view """
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.view_summary)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.view_tabs.addTab(tab, "Summary")

    def load_view_attack_tab(self):
        """ load MITRE ATT&CK tab view """
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.view_attack)

        tab = QtWidgets.QWidget()
        tab.setLayout(layout)

        self.view_tabs.addTab(tab, "MITRE")

    def load_file_menu(self):
        """ load file menu actions """
        actions = (
            ("Reset view", "Reset plugin view", self.reset),
            ("Run analysis", "Run capa analysis on current database", self.reload),
            ("Change rules directory...", "Select new rules directory", self.change_rules_dir),
            ("Export results...", "Export capa results as JSON file", self.export_json),
        )

        menu = self.view_menu_bar.addMenu("File")
        for (name, _, handle) in actions:
            action = QtWidgets.QAction(name, self.parent)
            action.triggered.connect(handle)
            menu.addAction(action)

    def export_json(self):
        """ export capa results as JSON file """
        if not self.doc:
            idaapi.info("No capa results to export.")
            return

        path = idaapi.ask_file(True, "*.json", "Choose file")

        if not path:
            return

        if os.path.exists(path) and 1 != idaapi.ask_yn(1, "File already exists. Overwrite?"):
            return

        with open(path, "wb") as export_file:
            export_file.write(
                json.dumps(self.doc, sort_keys=True, cls=capa.render.CapaJsonObjectEncoder).encode("utf-8")
            )

    def load_ida_hooks(self):
        """ load IDA Pro UI hooks """
        action_hooks = {
            "MakeName": self.ida_hook_rename,
            "EditFunction": self.ida_hook_rename,
        }

        self.ida_hooks = CapaExplorerIdaHooks(self.ida_hook_screen_ea_changed, action_hooks)
        self.ida_hooks.hook()

    def unload_ida_hooks(self):
        """ unload IDA Pro UI hooks """
        if self.ida_hooks:
            self.ida_hooks.unhook()

    def ida_hook_rename(self, meta, post=False):
        """hook for IDA rename action

        called twice, once before action and once after
        action completes

        @param meta: metadata cache
        @param post: indicates pre or post action
        """
        location = idaapi.get_screen_ea()
        if not location or not capa.ida.helpers.is_func_start(location):
            return

        curr_name = idaapi.get_name(location)

        if post:
            # post action update data model w/ current name
            self.model_data.update_function_name(meta.get("prev_name", ""), curr_name)
        else:
            # pre action so save current name for replacement later
            meta["prev_name"] = curr_name

    def ida_hook_screen_ea_changed(self, widget, new_ea, old_ea):
        """hook for IDA screen ea changed

        this hook is currently only relevant for limiting results displayed in the UI

        @param widget: IDA widget type
        @param new_ea: destination ea
        @param old_ea: source ea
        """
        if not self.view_limit_results_by_function.isChecked():
            # ignore if limit checkbox not selected
            return

        if idaapi.get_widget_type(widget) != idaapi.BWN_DISASM:
            # ignore views not the assembly view
            return

        if idaapi.get_func(new_ea) == idaapi.get_func(old_ea):
            # user navigated same function - ignore
            return

        self.limit_results_to_function(idaapi.get_func(new_ea))
        self.view_tree.resize_columns_to_content()

    def load_capa_results(self):
        """ run capa analysis and render results in UI """
        if not self.rule_path:
            rule_path = self.ask_user_directory()
            if not rule_path:
                capa.ida.helpers.inform_user_ida_ui("You must select a rules directory to use for analysis.")
                self.logger.warning("no rules directory selected. nothing to do.")
                return
            self.rule_path = rule_path

        self.logger.info("-" * 80)
        self.logger.info(" Using rules from %s." % self.rule_path)
        self.logger.info(" ")
        self.logger.info(" You can see the current default rule set here:")
        self.logger.info("     https://github.com/fireeye/capa-rules")
        self.logger.info("-" * 80)

        try:
            rules = capa.main.get_rules(self.rule_path)
            rules = capa.rules.RuleSet(rules)
        except (IOError, capa.rules.InvalidRule, capa.rules.InvalidRuleSet) as e:
            capa.ida.helpers.inform_user_ida_ui("Failed to load rules from %s" % self.rule_path)
            self.logger.error("failed to load rules from %s (%s)" % (self.rule_path, e))
            self.rule_path = ""
            return

        meta = capa.ida.helpers.collect_metadata()

        capabilities, counts = capa.main.find_capabilities(
            rules, capa.features.extractors.ida.IdaFeatureExtractor(), True
        )
        meta["analysis"].update(counts)

        # support binary files specifically for x86/AMD64 shellcode
        # warn user binary file is loaded but still allow capa to process it
        # TODO: check specific architecture of binary files based on how user configured IDA processors
        if idaapi.get_file_type_name() == "Binary file":
            self.logger.warning("-" * 80)
            self.logger.warning(" Input file appears to be a binary file.")
            self.logger.warning(" ")
            self.logger.warning(
                " capa currently only supports analyzing binary files containing x86/AMD64 shellcode with IDA."
            )
            self.logger.warning(
                " This means the results may be misleading or incomplete if the binary file loaded in IDA is not x86/AMD64."
            )
            self.logger.warning(
                " If you don't know the input file type, you can try using the `file` utility to guess it."
            )
            self.logger.warning("-" * 80)

            capa.ida.helpers.inform_user_ida_ui("capa encountered warnings during analysis")

        if capa.main.has_file_limitation(rules, capabilities, is_standalone=False):
            capa.ida.helpers.inform_user_ida_ui("capa encountered warnings during analysis")

        self.logger.info("analysis completed.")

        self.doc = capa.render.convert_capabilities_to_result_document(meta, rules, capabilities)

        self.model_data.render_capa_doc(self.doc)
        self.render_capa_doc_summary()
        self.render_capa_doc_mitre_summary()

        self.set_view_tree_default_sort_order()

        self.logger.info("render views completed.")

    def set_view_tree_default_sort_order(self):
        """ set capa tree view default sort order """
        self.view_tree.sortByColumn(CapaExplorerDataModel.COLUMN_INDEX_RULE_INFORMATION, QtCore.Qt.AscendingOrder)

    def render_capa_doc_summary(self):
        """ render capa summary results """
        for (row, rule) in enumerate(rutils.capability_rules(self.doc)):
            count = len(rule["matches"])

            if count == 1:
                capability = rule["meta"]["name"]
            else:
                capability = "%s (%d matches)" % (rule["meta"]["name"], count)

            self.view_summary.setRowCount(row + 1)

            self.view_summary.setItem(row, 0, self.render_new_table_header_item(capability))
            self.view_summary.setItem(row, 1, QtWidgets.QTableWidgetItem(rule["meta"]["namespace"]))

        # resize columns to content
        self.view_summary.resizeColumnsToContents()

    def render_capa_doc_mitre_summary(self):
        """ render capa MITRE ATT&CK results """
        tactics = collections.defaultdict(set)

        for rule in rutils.capability_rules(self.doc):
            if not rule["meta"].get("att&ck"):
                continue

            for attack in rule["meta"]["att&ck"]:
                tactic, _, rest = attack.partition("::")
                if "::" in rest:
                    technique, _, rest = rest.partition("::")
                    subtechnique, _, id = rest.rpartition(" ")
                    tactics[tactic].add((technique, subtechnique, id))
                else:
                    technique, _, id = rest.rpartition(" ")
                    tactics[tactic].add((technique, id))

        column_one = []
        column_two = []

        for (tactic, techniques) in sorted(tactics.items()):
            column_one.append(tactic.upper())
            # add extra space when more than one technique
            column_one.extend(["" for i in range(len(techniques) - 1)])

            for spec in sorted(techniques):
                if len(spec) == 2:
                    technique, id = spec
                    column_two.append("%s %s" % (technique, id))
                elif len(spec) == 3:
                    technique, subtechnique, id = spec
                    column_two.append("%s::%s %s" % (technique, subtechnique, id))
                else:
                    raise RuntimeError("unexpected ATT&CK spec format")

        self.view_attack.setRowCount(max(len(column_one), len(column_two)))

        for row, value in enumerate(column_one):
            self.view_attack.setItem(row, 0, self.render_new_table_header_item(value))

        for row, value in enumerate(column_two):
            self.view_attack.setItem(row, 1, QtWidgets.QTableWidgetItem(value))

        # resize columns to content
        self.view_attack.resizeColumnsToContents()

    def render_new_table_header_item(self, text):
        """ create new table header item with default style """
        item = QtWidgets.QTableWidgetItem(text)
        item.setForeground(QtGui.QColor(88, 139, 174))

        font = QtGui.QFont()
        font.setBold(True)

        item.setFont(font)

        return item

    def ida_reset(self):
        """ reset IDA UI """
        self.model_data.reset()
        self.view_tree.reset()
        self.view_limit_results_by_function.setChecked(False)
        self.set_view_tree_default_sort_order()

    def reload(self):
        """ reload views and re-run capa analysis """
        self.ida_reset()
        self.model_proxy.invalidate()
        self.model_data.clear()
        self.view_summary.setRowCount(0)
        self.load_capa_results()

        self.logger.info("reload complete.")
        idaapi.info("%s reload completed." % self.form_title)

    def reset(self, checked):
        """reset UI elements

        e.g. checkboxes and IDA highlighting
        """
        self.ida_reset()

        self.logger.info("reset completed.")
        idaapi.info("%s reset completed." % self.form_title)

    def slot_menu_bar_hovered(self, action):
        """display menu action tooltip

        @param action: QtWidgets.QAction*

        @reference: https://stackoverflow.com/questions/21725119/why-wont-qtooltips-appear-on-qactions-within-a-qmenu
        """
        QtWidgets.QToolTip.showText(
            QtGui.QCursor.pos(), action.toolTip(), self.view_menu_bar, self.view_menu_bar.actionGeometry(action)
        )

    def slot_checkbox_limit_by_changed(self, state):
        """slot activated if checkbox clicked

        if checked, configure function filter if screen location is located
        in function, otherwise clear filter
        """
        if state == QtCore.Qt.Checked:
            self.limit_results_to_function(idaapi.get_func(idaapi.get_screen_ea()))
        else:
            self.model_proxy.reset_address_range_filter()

        self.view_tree.reset()

    def limit_results_to_function(self, f):
        """add filter to limit results to current function

        @param f: (IDA func_t)
        """
        if f:
            self.model_proxy.add_address_range_filter(f.start_ea, f.end_ea)
        else:
            # if function not exists don't display any results (address should not be -1)
            self.model_proxy.add_address_range_filter(-1, -1)

    def ask_user_directory(self):
        """ create Qt dialog to ask user for a directory """
        return str(QtWidgets.QFileDialog.getExistingDirectory(self.parent, "Select rules directory"))

    def change_rules_dir(self):
        """ allow user to change rules directory """
        rule_path = self.ask_user_directory()
        if not rule_path:
            self.logger.warning("no rules directory selected. nothing to do.")
            return
        self.rule_path = rule_path
        if 1 == idaapi.ask_yn(1, "Run analysis now?"):
            self.reload()
