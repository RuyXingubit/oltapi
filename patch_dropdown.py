with open("frontend/lib/screens/unconfigured/authorize_onu_dialog.dart", "r") as f:
    content = f.read()

# For DropdownButtonFormField, 'value' is deprecated in favor of 'initialValue', but actually 'value' is still heavily used.
# Let's see the dart analyze error: "'value' is deprecated and shouldn't be used. Use initialValue instead"
# Wait, for DropdownButtonFormField, the parameter name is `value`. 
# Wait! In Flutter v3.33+, `DropdownButtonFormField.value` was deprecated!
# So I should use `initialValue` instead of `value`, and `onChanged` handles the state!
# Wait, if I use `initialValue`, I can't update it programmatically via setState without keys. But wait! I am using a `TextEditingController` as state.
# Wait, `DropdownButtonFormField` doesn't use `controller`.
# It's better to just replace `value:` with `initialValue:`.
# Oh, but if the items list changes, it might crash if the initialValue isn't in items.
content = content.replace("value: _vlanController.text.isNotEmpty ? _vlanController.text : null,", "initialValue: _vlanController.text.isNotEmpty ? _vlanController.text : null,")
content = content.replace("value: _profileController.text.isNotEmpty ? _profileController.text : null,", "initialValue: _profileController.text.isNotEmpty ? _profileController.text : null,")

with open("frontend/lib/screens/unconfigured/authorize_onu_dialog.dart", "w") as f:
    f.write(content)
