package com.practice.routine.ui

import android.content.Intent
import android.content.SharedPreferences
import android.media.RingtoneManager
import android.net.Uri
import android.os.Bundle
import android.widget.SeekBar
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.practice.routine.databinding.ActivitySettingsBinding

class SettingsActivity : AppCompatActivity() {

    private lateinit var binding: ActivitySettingsBinding
    private lateinit var prefs: SharedPreferences

    private val ringtoneLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val uri = result.data?.getParcelableExtra<Uri>(RingtoneManager.EXTRA_RINGTONE_PICKED_URI)
            prefs.edit().putString(PREF_ALARM_URI, uri?.toString()).apply()
        }
        updateAlarmNameDisplay()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)

        binding.toolbar.setNavigationOnClickListener { finish() }

        updateAlarmNameDisplay()
        setupVolumeSeekBar()

        binding.rowAlarmSound.setOnClickListener { openRingtonePicker() }
    }

    private fun updateAlarmNameDisplay() {
        val uriStr = prefs.getString(PREF_ALARM_URI, null)
        val name = if (uriStr != null) {
            try {
                RingtoneManager.getRingtone(this, Uri.parse(uriStr))?.getTitle(this) ?: "기본 알람"
            } catch (e: Exception) {
                "기본 알람"
            }
        } else {
            val defaultUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            try {
                RingtoneManager.getRingtone(this, defaultUri)?.getTitle(this) ?: "기본 알람"
            } catch (e: Exception) {
                "기본 알람"
            }
        }
        binding.tvAlarmName.text = name
    }

    private fun setupVolumeSeekBar() {
        val volume = prefs.getInt(PREF_ALARM_VOLUME, DEFAULT_VOLUME)
        binding.seekVolume.progress = volume
        binding.tvVolumeValue.text = "$volume%"

        binding.seekVolume.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar, progress: Int, fromUser: Boolean) {
                binding.tvVolumeValue.text = "$progress%"
            }
            override fun onStartTrackingTouch(seekBar: SeekBar) {}
            override fun onStopTrackingTouch(seekBar: SeekBar) {
                prefs.edit().putInt(PREF_ALARM_VOLUME, seekBar.progress).apply()
            }
        })
    }

    private fun openRingtonePicker() {
        val currentUriStr = prefs.getString(PREF_ALARM_URI, null)
        val intent = Intent(RingtoneManager.ACTION_RINGTONE_PICKER).apply {
            putExtra(RingtoneManager.EXTRA_RINGTONE_TYPE, RingtoneManager.TYPE_ALARM)
            putExtra(RingtoneManager.EXTRA_RINGTONE_TITLE, "알람 소리 선택")
            putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_SILENT, false)
            putExtra(RingtoneManager.EXTRA_RINGTONE_SHOW_DEFAULT, true)
            if (currentUriStr != null) {
                putExtra(RingtoneManager.EXTRA_RINGTONE_EXISTING_URI, Uri.parse(currentUriStr))
            } else {
                putExtra(
                    RingtoneManager.EXTRA_RINGTONE_EXISTING_URI,
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                )
            }
        }
        ringtoneLauncher.launch(intent)
    }

    companion object {
        const val PREFS_NAME = "app_settings"
        const val PREF_ALARM_URI = "pref_alarm_uri"
        const val PREF_ALARM_VOLUME = "pref_alarm_volume"
        const val DEFAULT_VOLUME = 80
    }
}
