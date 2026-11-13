package dev.kyungmin.watchcoach.phone

/** A workout and reference capture cannot claim the watch concurrently. */
internal object WorkoutRuntimeLock { val monitor = Any() }
