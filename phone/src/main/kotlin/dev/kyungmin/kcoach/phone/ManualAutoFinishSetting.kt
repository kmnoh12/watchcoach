package dev.kyungmin.kcoach.phone

import android.content.Context

internal object ManualAutoFinishSetting {
    fun isEnabled(context: Context) = context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE)
        .getBoolean("manualAutoFinish", true)
    fun setEnabled(context: Context, enabled: Boolean): Boolean {
        val saved = context.getSharedPreferences("ui-settings", Context.MODE_PRIVATE).edit().putBoolean("manualAutoFinish", enabled).commit()
        if (saved) {
            val store = SessionStore(context)
            store.loadActive().getOrNull()?.let {
                if (store.saveActive(it)) {
                    val bridge = PhoneWearBridge(context.applicationContext)
                    PhoneSessionController(store, bridge::sendRaw).resync()
                    bridge.closeAfterPendingDelivery()
                }
            }
        }
        return saved
    }
}
