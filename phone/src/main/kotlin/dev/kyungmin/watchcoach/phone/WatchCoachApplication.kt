package dev.kyungmin.watchcoach.phone

import android.app.Application
import dev.kyungmin.watchcoach.updates.*

class WatchCoachApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        LocalExitDiagnostics.install(this)
        WorkoutLaunchRecovery(this).recover().onFailure {
            android.util.Log.e("WatchCoachEvent", "Workout launch cleanup deferred", it)
        }
        val profiles = UserProfileStore(this)
        runCatching { profiles.migrate() }.onFailure {
            android.util.Log.e("WatchCoach", "Local profile migration failed; original personal facts retained", it)
        }
        runCatching { profiles.removeRetiredConnectionData() }.onFailure {
            android.util.Log.e("WatchCoach", "Retired connection cleanup will retry on next launch", it)
        }
        OtaCoordinator.initialize(this, OtaConfig(OtaRole.PHONE, BuildConfig.UPDATE_MANIFEST_URL))
    }
}
