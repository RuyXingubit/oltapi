with open("frontend/lib/screens/olts/olt_form_dialog.dart", "r") as f:
    content = f.read()

content = content.replace("value: _currentModels.contains(_modelCtrl.text) ? _modelCtrl.text : (_currentModels.isNotEmpty ? _currentModels.first : null),", "initialValue: _currentModels.contains(_modelCtrl.text) ? _modelCtrl.text : (_currentModels.isNotEmpty ? _currentModels.first : null),")

with open("frontend/lib/screens/olts/olt_form_dialog.dart", "w") as f:
    f.write(content)
