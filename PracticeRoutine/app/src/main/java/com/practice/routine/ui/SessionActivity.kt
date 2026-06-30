package com.practice.routine.ui

import android.content.*
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.*
import android.view.View
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.practice.routine.R
import com.practice.routine.data.RoutineItem
import com.practice.routine.databinding.ActivitySessionBinding
import com.practice.routine.service.TimerService

class SessionActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySessionBinding
    private var items: ArrayList<RoutineItem> = arrayListOf()
    private var currentIndex = 0
    private var isPaused = false
    private var alarmPlayer: MediaPlayer? = null

    private val tickReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val index = intent.getIntExtra(TimerService.EXTRA_CURRENT_INDEX, 0)
            val remaining = intent.getLongExtra(TimerService.EXTRA_REMAINING_SECONDS, 0)
            val set = intent.getIntExtra(TimerService.EXTRA_CURRENT_SET, 1)
            val total = intent.getIntExtra(TimerService.EXTRA_TOTAL_SETS, 1)
            currentIndex = index
            updateUI(index, remaining)
            updateSetLabel(set, total)
        }
    }

    private val stepDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val doneIndex = intent.getIntExtra(TimerService.EXTRA_CURRENT_INDEX, 0)
            val set = intent.getIntExtra(TimerService.EXTRA_CURRENT_SET, 1)
            val total = intent.getIntExtra(TimerService.EXTRA_TOTAL_SETS, 1)
            markItemDone(doneIndex)
            updateSetLabel(set, total)
            // 서비스는 '대기' 상태일 때만 STEP_DONE 을 보냄(전체 완료는 ALL_DONE)
            showNextConfirmUI(doneIndex)
        }
    }

    private val allDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            showAllDone()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySessionBinding.inflate(layoutInflater)
        setContentView(binding.root)

        @Suppress("UNCHECKED_CAST")
        items = intent.getParcelableArrayListExtra(EXTRA_ITEMS) ?: arrayListOf()

        if (items.isEmpty()) {
            Toast.makeText(this, "루틴이 없습니다.", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        binding.toolbar.setNavigationOnClickListener { onBackPressedDispatcher.onBackPressed() }
        setupButtons()
        setupBackHandler()
        initUI()
        if (!TimerService.isRunning) {
            startTimerService()
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
    }

    private fun initUI() {
        val item = items[0]
        binding.tvCurrentStep.text = "1 / ${items.size}"
        binding.tvCurrentName.text = item.name
        binding.tvTimer.text = String.format("%02d:00", item.durationMinutes)
        binding.progressTimer.max = item.durationMinutes * 60
        binding.progressTimer.progress = item.durationMinutes * 60
        setRingColor(R.color.primary)
        binding.tvPausedLabel.visibility = View.GONE
        updateNextCard(0)
        updateNote(0)
        updateSetLabel(1, items[0].repeatCount)
    }

    private fun updateSetLabel(currentSet: Int, totalSets: Int) {
        if (totalSets > 1) {
            binding.tvSetLabel.text = "$currentSet/$totalSets 세트"
            binding.tvSetLabel.visibility = View.VISIBLE
        } else {
            binding.tvSetLabel.visibility = View.GONE
        }
    }

    private fun updateNote(index: Int) {
        val note = items.getOrNull(index)?.note?.trim()
        if (!note.isNullOrEmpty()) {
            binding.tvNote.text = note
            binding.noteCard.visibility = View.VISIBLE
        } else {
            binding.noteCard.visibility = View.GONE
        }
    }

    private fun updateNextCard(index: Int) {
        val next = items.getOrNull(index + 1)
        if (next != null) {
            binding.nextCard.visibility = View.VISIBLE
            binding.tvNextStep.text = "${next.name} · ${next.durationMinutes}분"
        } else {
            binding.nextCard.visibility = View.INVISIBLE
        }
    }

    private fun setRingColor(colorRes: Int) {
        binding.progressTimer.setIndicatorColor(
            androidx.core.content.ContextCompat.getColor(this, colorRes)
        )
    }

    private fun setupButtons() {
        binding.btnPauseResume.setOnClickListener {
            isPaused = !isPaused
            val action = if (isPaused) TimerService.ACTION_PAUSE else TimerService.ACTION_RESUME
            startService(Intent(this, TimerService::class.java).apply { this.action = action })
            binding.btnPauseResume.text = if (isPaused) "재개" else "일시정지"
            binding.btnPauseResume.setIconResource(if (isPaused) R.drawable.ic_play_filled else R.drawable.ic_pause)
            binding.tvPausedLabel.visibility = if (isPaused) View.VISIBLE else View.GONE
            setRingColor(if (isPaused) R.color.hint else R.color.primary)
        }

        binding.btnNext.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("다음 루틴으로")
                .setMessage("현재 루틴을 건너뛰고 다음으로 이동할까요?")
                .setPositiveButton("예") { _, _ ->
                    stopAlarm()
                    binding.btnConfirmNext.visibility = View.GONE
                    binding.btnPauseResume.isEnabled = true
                    binding.btnNext.isEnabled = true
                    startService(Intent(this, TimerService::class.java).apply {
                        action = TimerService.ACTION_NEXT
                    })
                }
                .setNegativeButton("아니오", null)
                .show()
        }

        binding.btnStop.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("루틴 중지")
                .setMessage("연습 루틴을 중지할까요?")
                .setPositiveButton("중지") { _, _ ->
                    stopAlarm()
                    startService(Intent(this, TimerService::class.java).apply {
                        action = TimerService.ACTION_STOP
                    })
                    finish()
                }
                .setNegativeButton("취소", null)
                .show()
        }
    }

    private fun setupBackHandler() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                AlertDialog.Builder(this@SessionActivity)
                    .setTitle("루틴 계속 진행")
                    .setMessage("뒤로 가도 타이머는 백그라운드에서 계속 실행됩니다.")
                    .setPositiveButton("확인") { _, _ ->
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                    .setNegativeButton("취소", null)
                    .show()
            }
        })
    }

    private fun startTimerService() {
        val intent = Intent(this, TimerService::class.java).apply {
            action = TimerService.ACTION_START
            putParcelableArrayListExtra(TimerService.EXTRA_ITEMS, items)
        }
        startForegroundService(intent)
    }

    private fun showNextConfirmUI(doneIndex: Int) {
        val prefs = getSharedPreferences(SettingsActivity.PREFS_NAME, MODE_PRIVATE)
        val uriStr = prefs.getString(SettingsActivity.PREF_ALARM_URI, null)
        val volumePct = prefs.getInt(SettingsActivity.PREF_ALARM_VOLUME, SettingsActivity.DEFAULT_VOLUME)
        val volume = volumePct / 100f

        val alarmUri = if (uriStr != null) Uri.parse(uriStr)
        else (RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))

        try {
            alarmPlayer = MediaPlayer.create(this, alarmUri)?.also {
                it.setVolume(volume, volume)
                it.isLooping = true
                it.start()
            }
        } catch (e: Exception) {
            // 알람 재생 실패 시 무음으로 진행
        }

        binding.tvTimer.text = "00:00"
        binding.tvTimer.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.error))
        binding.progressTimer.progress = 0
        setRingColor(R.color.error)
        binding.tvPausedLabel.visibility = View.GONE
        binding.controlRow.visibility = View.GONE
        binding.btnConfirmNext.visibility = View.VISIBLE

        binding.btnConfirmNext.setOnClickListener {
            stopAlarm()
            binding.btnConfirmNext.visibility = View.GONE
            binding.controlRow.visibility = View.VISIBLE
            binding.tvTimer.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))
            setRingColor(R.color.primary)
            binding.btnPauseResume.text = "일시정지"
            isPaused = false
            startService(Intent(this, TimerService::class.java).apply {
                action = TimerService.ACTION_CONFIRM_NEXT
            })
        }
    }

    private fun stopAlarm() {
        alarmPlayer?.stop()
        alarmPlayer?.release()
        alarmPlayer = null
    }

    private fun updateUI(index: Int, remainingSeconds: Long) {
        if (index >= items.size) return
        val item = items[index]
        val mins = remainingSeconds / 60
        val secs = remainingSeconds % 60

        binding.tvCurrentStep.text = "${index + 1} / ${items.size}"
        binding.tvCurrentName.text = item.name
        binding.tvTimer.text = String.format("%02d:%02d", mins, secs)
        binding.tvTimer.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))

        val totalSeconds = item.durationMinutes * 60
        binding.progressTimer.max = totalSeconds
        binding.progressTimer.progress = remainingSeconds.toInt()

        binding.tvPausedLabel.visibility = if (isPaused) View.VISIBLE else View.GONE
        setRingColor(if (isPaused) R.color.hint else R.color.primary)

        updateNextCard(index)
        updateNote(index)
    }

    private fun markItemDone(index: Int) {
        // 세션 화면이 원형 타이머 중심으로 바뀌어 목록 표시는 사용하지 않음
    }

    private fun showAllDone() {
        stopAlarm()
        binding.btnConfirmNext.visibility = View.GONE
        binding.controlRow.visibility = View.GONE
        binding.tvCurrentName.text = "모든 루틴 완료! 👏"
        binding.tvTimer.text = "00:00"
        binding.tvTimer.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.accent))
        binding.tvCurrentStep.text = "${items.size} / ${items.size}"
        binding.nextCard.visibility = View.INVISIBLE
        binding.noteCard.visibility = View.GONE
        binding.tvPausedLabel.visibility = View.GONE
        binding.tvSetLabel.visibility = View.GONE
        binding.progressTimer.progress = binding.progressTimer.max
        setRingColor(R.color.accent)

        AlertDialog.Builder(this)
            .setTitle("완료!")
            .setMessage("모든 연습 루틴을 완료했습니다! 수고하셨습니다.")
            .setPositiveButton("확인") { _, _ -> finish() }
            .setCancelable(false)
            .show()
    }

    override fun onResume() {
        super.onResume()
        registerReceiver(tickReceiver, IntentFilter(TimerService.BROADCAST_TICK),
            RECEIVER_NOT_EXPORTED)
        registerReceiver(stepDoneReceiver, IntentFilter(TimerService.BROADCAST_STEP_DONE),
            RECEIVER_NOT_EXPORTED)
        registerReceiver(allDoneReceiver, IntentFilter(TimerService.BROADCAST_ALL_DONE),
            RECEIVER_NOT_EXPORTED)

        // 앱이 백그라운드에 있는 동안 단계/세트가 완료돼 대기 중이면 버튼으로 복원
        val waitIdx = TimerService.waitingIndex
        if (waitIdx >= 0) {
            val total = items.getOrNull(waitIdx)?.repeatCount ?: 1
            updateSetLabel(TimerService.currentSet, total)
            showNextConfirmUI(waitIdx)
        }
    }

    override fun onPause() {
        super.onPause()
        stopAlarm()
        unregisterReceiver(tickReceiver)
        unregisterReceiver(stepDoneReceiver)
        unregisterReceiver(allDoneReceiver)
    }

    companion object {
        const val EXTRA_ITEMS = "EXTRA_ITEMS"
    }
}
