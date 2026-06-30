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
        const val ACTION_CONFIRM_NEXT = "ACTION_CONFIRM_NEXT"
        const val EXTRA_ITEMS = "EXTRA_ITEMS"
        const val CHANNEL_ID = "practice_timer_channel"
        const val NOTIF_ID = 1001

        const val BROADCAST_TICK = "com.practice.routine.TICK"
        const val BROADCAST_STEP_DONE = "com.practice.routine.STEP_DONE"
        const val BROADCAST_ALL_DONE = "com.practice.routine.ALL_DONE"
        const val EXTRA_CURRENT_INDEX = "EXTRA_CURRENT_INDEX"
        const val EXTRA_REMAINING_SECONDS = "EXTRA_REMAINING_SECONDS"
        const val EXTRA_CURRENT_SET = "EXTRA_CURRENT_SET"
        const val EXTRA_TOTAL_SETS = "EXTRA_TOTAL_SETS"
        const val EXTRA_IS_SET_ADVANCE = "EXTRA_IS_SET_ADVANCE"

        @Volatile var isRunning = false
        // 완료 후 확인 대기 중인 단계 인덱스. -1이면 대기 중 아님
        @Volatile var waitingIndex = -1
        // 현재 진행 중인 세트(1-base). 화면 회전/백그라운드 복원용 static
        @Volatile var currentSet = 1
        // 대기 중인 전환이 '세트 전환'이면 true, '단계 전환'이면 false
        @Volatile var waitingIsSetAdvance = false
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
                    currentSet = 1
                    waitingIndex = -1
                    waitingIsSetAdvance = false
                    startCurrentStep()
                }
            }
            ACTION_PAUSE -> pauseTimer()
            ACTION_RESUME -> resumeTimer()
            ACTION_STOP -> stopSelf()
            ACTION_NEXT -> skipToNext()
            ACTION_CONFIRM_NEXT -> confirmAndStartNext()
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
        val item = items.getOrNull(currentIndex) ?: return
        val moreSetsInStep = currentSet < item.repeatCount
        val moreSteps = currentIndex < items.size - 1

        sendStepDoneNotification()

        if (!moreSetsInStep && !moreSteps) {
            // 마지막 단계의 마지막 세트 - 전체 완료(완주). 기록 후 종료.
            currentIndex++
            broadcastAllDone()
            logPracticeAndStop()
        } else {
            // 세트 전환 또는 단계 전환 대기
            waitingIndex = currentIndex
            waitingIsSetAdvance = moreSetsInStep
            broadcastStepDone()
            showWaitingNotification()
        }
    }

    private fun confirmAndStartNext() {
        if (waitingIndex < 0) return
        if (waitingIsSetAdvance) beginNextSet() else beginNextStep()
    }

    // 완주 시에만 연습 기록 저장. stopSelf 가 서비스 scope 를 취소하므로
    // insert 는 독립 IO scope 에서 실행하고, 완료 후 종료한다.
    private fun logPracticeAndStop() {
        val completedItems = ArrayList(items)
        if (completedItems.isEmpty()) { stopSelf(); return }
        val name = if (completedItems.size == 1) completedItems[0].name
            else "${completedItems[0].name} 외 ${completedItems.size - 1}개"
        val durationSeconds = completedItems.sumOf { it.durationMinutes * 60 * it.repeatCount }
        val log = com.practice.routine.data.PracticeLog(
            routineName = name,
            completedAt = System.currentTimeMillis(),
            durationSeconds = durationSeconds,
            stepCount = completedItems.size
        )
        val appContext = applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            try {
                com.practice.routine.data.RoutineDatabase.getInstance(appContext)
                    .practiceLogDao().insert(log)
            } catch (_: Exception) {
            } finally {
                stopSelf()
            }
        }
    }

    // 세트 전환 지점 - 향후 '세트 사이 휴식'을 여기에 끼우면 됨
    private fun beginNextSet() {
        waitingIndex = -1
        waitingIsSetAdvance = false
        currentSet++
        startCurrentStep()
    }

    // 단계 전환 지점
    private fun beginNextStep() {
        waitingIndex = -1
        waitingIsSetAdvance = false
        currentIndex++
        currentSet = 1
        startCurrentStep()
    }

    fun pauseTimer() {
        isPaused = true
    }

    fun resumeTimer() {
        isPaused = false
    }

    // 스킵: 현재 단계의 남은 세트까지 모두 건너뛰고 다음 단계로
    fun skipToNext() {
        timerJob?.cancel()
        waitingIndex = -1
        waitingIsSetAdvance = false
        currentIndex++
        currentSet = 1
        startCurrentStep()
    }

    private fun broadcastTick() {
        val total = items.getOrNull(currentIndex)?.repeatCount ?: 1
        sendBroadcast(Intent(BROADCAST_TICK).apply {
            setPackage(packageName)
            putExtra(EXTRA_CURRENT_INDEX, currentIndex)
            putExtra(EXTRA_REMAINING_SECONDS, remainingSeconds)
            putExtra(EXTRA_CURRENT_SET, currentSet)
            putExtra(EXTRA_TOTAL_SETS, total)
        })
    }

    private fun broadcastStepDone() {
        val total = items.getOrNull(currentIndex)?.repeatCount ?: 1
        sendBroadcast(Intent(BROADCAST_STEP_DONE).apply {
            setPackage(packageName)
            putExtra(EXTRA_CURRENT_INDEX, currentIndex)
            putExtra(EXTRA_CURRENT_SET, currentSet)
            putExtra(EXTRA_TOTAL_SETS, total)
            putExtra(EXTRA_IS_SET_ADVANCE, waitingIsSetAdvance)
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
            "'${currentItem.name}' 완료! 앱을 열어 다음 루틴을 시작하세요."
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

    private fun showWaitingNotification() {
        val doneItem = items.getOrNull(waitingIndex) ?: return
        val nextItem = items.getOrNull(waitingIndex + 1)

        // 세트 전환이면 같은 단계의 다음 세트, 아니면 다음 단계를 안내
        val nextLabel: String
        val bigLabel: String
        if (waitingIsSetAdvance) {
            nextLabel = "${doneItem.name} · ${currentSet + 1}/${doneItem.repeatCount}세트"
            bigLabel = "다음 세트: '${doneItem.name}' (${currentSet + 1}/${doneItem.repeatCount})\n준비되면 '다음 시작' 버튼을 눌러주세요."
        } else if (nextItem != null) {
            nextLabel = "${nextItem.name} (${nextItem.durationMinutes}분)"
            bigLabel = "다음: '${nextItem.name}' (${nextItem.durationMinutes}분)\n준비되면 '다음 시작' 버튼을 눌러주세요."
        } else {
            nextLabel = ""
            bigLabel = "준비되면 '다음 시작' 버튼을 눌러주세요."
        }

        val sessionIntent = Intent(this, SessionActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP
            putParcelableArrayListExtra(SessionActivity.EXTRA_ITEMS, items)
        }
        val pi = PendingIntent.getActivity(
            this, 0, sessionIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val confirmIntent = Intent(this, TimerService::class.java).apply {
            action = ACTION_CONFIRM_NEXT
        }
        val confirmPi = PendingIntent.getService(
            this, 4, confirmIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = Intent(this, TimerService::class.java).apply { action = ACTION_STOP }
        val stopPi = PendingIntent.getService(
            this, 3, stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIF_ID, NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_timer)
            .setContentTitle("'${doneItem.name}' 완료!")
            .setContentText(if (nextLabel.isNotEmpty()) "다음: $nextLabel" else "준비되면 '다음 시작'을 눌러주세요.")
            .setStyle(NotificationCompat.BigTextStyle().bigText(bigLabel))
            .setOngoing(true)
            .setContentIntent(pi)
            .addAction(R.drawable.ic_skip, "다음 시작", confirmPi)
            .addAction(R.drawable.ic_stop, "중지", stopPi)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
        )
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
        val totalSets = items.getOrNull(currentIndex)?.repeatCount ?: 1
        val progress = if (totalSets > 1)
            "${currentIndex + 1}/${items.size} · 세트 $currentSet/$totalSets"
        else
            "${currentIndex + 1}/${items.size}"

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
        waitingIndex = -1
        waitingIsSetAdvance = false
        currentSet = 1
        timerJob?.cancel()
        scope.cancel()
        super.onDestroy()
    }
}
