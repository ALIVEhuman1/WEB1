package com.practice.routine.ui

import android.content.*
import android.os.*
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.practice.routine.data.RoutineItem
import com.practice.routine.databinding.ActivitySessionBinding
import com.practice.routine.service.TimerService

class SessionActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySessionBinding
    private var items: ArrayList<RoutineItem> = arrayListOf()
    private var currentIndex = 0
    private var isPaused = false

    private val tickReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val index = intent.getIntExtra(TimerService.EXTRA_CURRENT_INDEX, 0)
            val remaining = intent.getLongExtra(TimerService.EXTRA_REMAINING_SECONDS, 0)
            currentIndex = index
            updateUI(index, remaining)
        }
    }

    private val stepDoneReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            val doneIndex = intent.getIntExtra(TimerService.EXTRA_CURRENT_INDEX, 0)
            markItemDone(doneIndex)
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

        setupList()
        setupButtons()
        initUI()
        startService()
    }

    private fun initUI() {
        val item = items[0]
        binding.tvCurrentStep.text = "1/${items.size}"
        binding.tvCurrentName.text = item.name
        binding.tvTimer.text = String.format("%02d:00", item.durationMinutes)
        binding.progressTimer.max = item.durationMinutes * 60
        binding.progressTimer.progress = 0
        val next = items.getOrNull(1)
        if (next != null) {
            binding.tvNextLabel.visibility = View.VISIBLE
            binding.tvNextStep.visibility = View.VISIBLE
            binding.tvNextStep.text = "다음: ${next.name} (${next.durationMinutes}분)"
        } else {
            binding.tvNextLabel.visibility = View.INVISIBLE
            binding.tvNextStep.visibility = View.INVISIBLE
        }
    }

    private fun setupList() {
        binding.tvTotalRoutines.text = "총 ${items.size}개 루틴 · 총 ${items.sumOf { it.durationMinutes }}분"
        val adapter = SessionRoutineAdapter(items)
        binding.rvSessionList.adapter = adapter
    }

    private fun setupButtons() {
        binding.btnPauseResume.setOnClickListener {
            isPaused = !isPaused
            val action = if (isPaused) TimerService.ACTION_PAUSE else TimerService.ACTION_RESUME
            startService(Intent(this, TimerService::class.java).apply { this.action = action })
            binding.btnPauseResume.text = if (isPaused) "재개" else "일시정지"
        }

        binding.btnNext.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("다음 루틴으로")
                .setMessage("현재 루틴을 건너뛰고 다음으로 이동할까요?")
                .setPositiveButton("예") { _, _ ->
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
                    startService(Intent(this, TimerService::class.java).apply {
                        action = TimerService.ACTION_STOP
                    })
                    finish()
                }
                .setNegativeButton("취소", null)
                .show()
        }
    }

    private fun startService() {
        val intent = Intent(this, TimerService::class.java).apply {
            action = TimerService.ACTION_START
            putParcelableArrayListExtra(TimerService.EXTRA_ITEMS, items)
        }
        startForegroundService(intent)
    }

    private fun updateUI(index: Int, remainingSeconds: Long) {
        if (index >= items.size) return
        val item = items[index]
        val mins = remainingSeconds / 60
        val secs = remainingSeconds % 60

        binding.tvCurrentStep.text = "${index + 1}/${items.size}"
        binding.tvCurrentName.text = item.name
        binding.tvTimer.text = String.format("%02d:%02d", mins, secs)

        val totalSeconds = item.durationMinutes * 60
        val elapsed = totalSeconds - remainingSeconds
        binding.progressTimer.max = totalSeconds
        binding.progressTimer.progress = elapsed.toInt()

        val next = items.getOrNull(index + 1)
        if (next != null) {
            binding.tvNextLabel.visibility = View.VISIBLE
            binding.tvNextStep.visibility = View.VISIBLE
            binding.tvNextStep.text = "다음: ${next.name} (${next.durationMinutes}분)"
        } else {
            binding.tvNextLabel.visibility = View.INVISIBLE
            binding.tvNextStep.visibility = View.INVISIBLE
        }
    }

    private fun markItemDone(index: Int) {
        (binding.rvSessionList.adapter as? SessionRoutineAdapter)?.markDone(index)
    }

    private fun showAllDone() {
        binding.tvCurrentName.text = "모든 루틴 완료!"
        binding.tvTimer.text = "00:00"
        binding.tvCurrentStep.text = "${items.size}/${items.size}"
        binding.btnPauseResume.isEnabled = false
        binding.btnNext.isEnabled = false
        binding.progressTimer.progress = binding.progressTimer.max

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
    }

    override fun onPause() {
        super.onPause()
        unregisterReceiver(tickReceiver)
        unregisterReceiver(stepDoneReceiver)
        unregisterReceiver(allDoneReceiver)
    }

    override fun onBackPressed() {
        AlertDialog.Builder(this)
            .setTitle("루틴 계속 진행")
            .setMessage("뒤로 가도 타이머는 백그라운드에서 계속 실행됩니다.")
            .setPositiveButton("확인") { _, _ -> super.onBackPressed() }
            .setNegativeButton("취소", null)
            .show()
    }

    companion object {
        const val EXTRA_ITEMS = "EXTRA_ITEMS"
    }
}
