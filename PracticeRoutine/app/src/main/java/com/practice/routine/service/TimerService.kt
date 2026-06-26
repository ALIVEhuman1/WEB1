package com.practice.routine.service

import android.app.*
import android.content.Intent
import android.media.RingtoneManager
import android.os.*
import androidx.core.app.NotificationCompat
import com.practice.routine.R
import com.practice.routine.data.RoutineItem
import com.practice.routine.ui.SessionActivity
import kotlinx.coroutines.*

class TimerService : Service() {

    companion object {
        const val ACTION_START = "ACTION_START"
        const val ACTION_PAUSE = "ACTION_PAUSE"
        const val ACTION_RESUME = "ACTION_RESUME"
        const val ACTION_STOP = "ACTION_STOP"
        const val ACTION_NEXT = "ACTION_NEXT"
        const val EXTRA_ITEMS = "EXTRA_ITEMS"
        const val CHANNEL_ID = "practice_timer_channel"
        const val NOTIF_ID = 1001

        const val BROADCAST_TICK = "com.practice.routine.TICK"
        const val BROADCAST_STEP_DONE = "com.practice.routine.STEP_DONE"
        const val BROADCAST_ALL_DONE = "com.practice.routine.ALL_DONE"
        const val EXTRA_CURRENT_INDEX = "EXTRA_CURRENT_INDEX"
        const val EXTRA_REMAINING_SECONDS = "EXTRA_REMAINING_SECONDS"

        @Volatile var isRunning = false
    }

    private val binder = TimerBinder()
    private var items: ArrayList<RoutineItem> = arrayListOf()
    private var currentIndex = 0
    private var remainingSeconds = 0L
    private var isPaused = false
    private var timerJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    inner class TimerBinder : Binder() {
        fun getService() = this@TimerService
    }

    override fun onBind(intent: Intent?) = binder

    override fun onCreate() {
        super.onCreate()
        isRunning = true
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                @Suppress("UNCHECKED_CAST")
                val newItems = intent.getParcelableArrayListExtra<RoutineItem>(EXTRA_ITEMS)
                if (newItems != null) {
                    items = newItems
                    currentIndex = 0
                    startCurrentStep()
                }
            }
            ACTION_PAUSE -> pauseTimer()
            ACTION_RESUME -> resumeTimer()
            ACTION_STOP -> stopSelf()
            ACTION_NEXT -> skipToNext()
        }
        return START_NOT_STICKY
    }

    private fun startCurrentStep() {
        if (currentIndex >= items.size) {
            broadcastAllDone()
            stopSelf()
            return
        }
        val item = items[currentIndex]
        remainingSeconds = item.durationMinutes * 60L
        isPaused = false
        startForeground(NOTIF_ID, buildNotification(item.name, remainingSeconds))
        runTimer()
    }

    private fun runTimer() {
        timerJob?.cancel()
        timerJob = scope.launch {
            while (remainingSeconds > 0) {
                if (!isPaused) {
                    broadcastTick()
                    updateNotification()
                    delay(1000L)
                    remainingSeconds--
                } else {
                    delay(200L)
                }
            }
            onStepComplete()
        }
    }

    private fun onStepComplete() {
        sendStepDoneNotification()
        broadcastStepDone()
        currentIndex++
        if (currentIndex < items.size) {
            startCurrentStep()
        } else {
            broadcastAllDone()
            stopSelf()
        }
    }

    fun pauseTimer() {
        isPaused = true
    }

    fun resumeTimer() {
        isPaused = false
    }

    fun skipToNext() {
        timerJob?.cancel()
        currentIndex++
        startCurrentStep()
    }

    private fun broadcastTick() {
        sendBroadcast(Intent(BROADCAST_TICK).apply {
            setPackage(packageName)
            putExtra(EXTRA_CURRENT_INDEX, currentIndex)
            putExtra(EXTRA_REMAINING_SECONDS, remainingSeconds)
        })
    }

    private fun broadcastStepDone() {
        sendBroadcast(Intent(BROADCAST_STEP_DONE).apply {
            setPackage(packageName)
            putExtra(EXTRA_CURRENT_INDEX, currentIndex)
        })
    }

    private fun broadcastAllDone() {
        sendBroadcast(Intent(BROADCAST_ALL_DONE).apply {
            setPackage(packageName)
        })
    }

    private fun sendStepDoneNotification() {
        val currentItem = items.getOrNull(currentIndex) ?: return
        val nextItem = items.getOrNull(currentIndex + 1)
        val sound = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)

        val text = if (nextItem != null)
            "'${currentItem.name}' 완료! 다음: '${nextItem.name}' (${nextItem.durationMinutes}분)"
        else
            "'${currentItem.name}' 완료! 모든 루틴 끝!"

        val notif = NotificationCompat.Builder(this, CHANNEL_ID + "_step")
            .setSmallIcon(R.drawable.ic_timer)
            .setContentTitle("연습 완료")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setSound(sound)
            .setVibrate(longArrayOf(0, 500, 200, 500))
            .setAutoCancel(true)
            .build()

        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID + currentIndex + 10, notif)
    }

    private fun buildNotification(name: String, secondsLeft: Long): Notification {
        val sessionIntent = Intent(this, SessionActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            putParcelableArrayListExtra(SessionActivity.EXTRA_ITEMS, items)
        }
        val pi = PendingIntent.getActivity(
            this, 0, sessionIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val pauseResumeIntent = Intent(this, TimerService::class.java).apply {
            action = if (isPaused) ACTION_RESUME else ACTION_PAUSE
        }
        val pausePi = PendingIntent.getService(
            this, 1, pauseResumeIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val nextIntent = Intent(this, TimerService::class.java).apply { action = ACTION_NEXT }
        val nextPi = PendingIntent.getService(
            this, 2, nextIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(this, TimerService::class.java).apply { action = ACTION_STOP }
        val stopPi = PendingIntent.getService(
            this, 3, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val mins = secondsLeft / 60
        val secs = secondsLeft % 60
        val progress = "${currentIndex + 1}/${items.size}"

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_timer)
            .setContentTitle("[$progress] $name")
            .setContentText(String.format("%02d:%02d 남음", mins, secs))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(pi)
            .addAction(R.drawable.ic_pause, if (isPaused) "재개" else "일시정지", pausePi)
            .addAction(R.drawable.ic_skip, "다음", nextPi)
            .addAction(R.drawable.ic_stop, "중지", stopPi)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotification() {
        val item = items.getOrNull(currentIndex) ?: return
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, buildNotification(item.name, remainingSeconds))
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "연습 타이머",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "연습 루틴 타이머 알림"
            setShowBadge(false)
        }
        val stepChannel = NotificationChannel(
            CHANNEL_ID + "_step",
            "단계 완료 알림",
            NotificationManager.IMPORTANCE_HIGH
        ).apply {
            description = "각 연습 단계 완료 시 알림"
            enableVibration(true)
        }
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(channel)
        nm.createNotificationChannel(stepChannel)
    }

    override fun onDestroy() {
        isRunning = false
        timerJob?.cancel()
        scope.cancel()
        super.onDestroy()
    }
}
