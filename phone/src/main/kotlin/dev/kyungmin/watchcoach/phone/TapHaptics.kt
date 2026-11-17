package dev.kyungmin.watchcoach.phone

import android.app.AlertDialog
import android.app.Dialog
import android.content.Context
import android.content.DialogInterface
import android.view.View
import android.widget.Spinner
import dev.kyungmin.watchcoach.phone.ui.performTapHaptic

/** Click listeners also cover accessibility clicks and never run for a programmatic checked-state update. */
internal fun View.setOnTapClickListener(listener: View.OnClickListener) {
    setOnClickListener { view ->
        if (view.isEnabled) {
            view.performTapHaptic()
            listener.onClick(view)
        }
    }
}

private fun DialogInterface.tapHaptic() {
    (this as Dialog).window?.decorView?.performTapHaptic()
}

// Keep AlertDialog's normal dismissal and nullable listeners, including Cancel buttons.
internal fun AlertDialog.Builder.setTapPositiveButton(text: CharSequence, listener: DialogInterface.OnClickListener?): AlertDialog.Builder =
    setPositiveButton(text) { dialog, which -> dialog.tapHaptic(); listener?.onClick(dialog, which) }

internal fun AlertDialog.Builder.setTapNegativeButton(text: CharSequence, listener: DialogInterface.OnClickListener?): AlertDialog.Builder =
    setNegativeButton(text) { dialog, which -> dialog.tapHaptic(); listener?.onClick(dialog, which) }

internal fun AlertDialog.Builder.setTapItems(items: Array<String>, listener: DialogInterface.OnClickListener): AlertDialog.Builder =
    setItems(items) { dialog, which -> dialog.tapHaptic(); listener.onClick(dialog, which) }

internal fun AlertDialog.Builder.setTapMultiChoiceItems(items: Array<String>, checked: BooleanArray,
    listener: DialogInterface.OnMultiChoiceClickListener): AlertDialog.Builder =
    setMultiChoiceItems(items, checked) { dialog, which, value -> dialog.tapHaptic(); listener.onClick(dialog, which, value) }

/** Spinner opens through performClick for both touch and accessibility. Initial selection stays silent. */
internal class TapSpinner(context: Context) : Spinner(context) {
    override fun performClick(): Boolean {
        if (isEnabled) performTapHaptic()
        return super.performClick()
    }
}
