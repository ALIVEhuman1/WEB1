package com.practice.routine.ui

import android.content.Intent
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.practice.routine.data.RoutineDatabase
import com.practice.routine.data.RoutineRepository
import com.practice.routine.databinding.ActivityMapBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MapActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMapBinding
    private val db by lazy { RoutineDatabase.getInstance(this) }
    private val repo by lazy { RoutineRepository(db.routineDao(), db.presetDao(), db.branchDao()) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMapBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.toolbar.inflateMenu(com.practice.routine.R.menu.menu_map)
        binding.toolbar.setOnMenuItemClickListener {
            if (it.itemId == com.practice.routine.R.id.action_reset_view) { binding.mindMap.resetView(); true } else false
        }

        binding.btnEdit.setOnClickListener {
            startActivity(Intent(this, com.practice.routine.MainActivity::class.java))
        }
        binding.btnStart.setOnClickListener {
            startActivity(Intent(this, com.practice.routine.MainActivity::class.java).apply {
                putExtra(com.practice.routine.MainActivity.EXTRA_START_NOW, true)
            })
        }

        binding.mindMap.onChoiceTap = { choiceItemId ->
            startActivity(Intent(this, BranchEditActivity::class.java).apply {
                putExtra(BranchEditActivity.EXTRA_CHOICE_ITEM_ID, choiceItemId)
            })
        }
        binding.mindMap.onStepTap = { name, info ->
            AlertDialog.Builder(this)
                .setTitle(name)
                .setMessage(info)
                .setPositiveButton("확인", null)
                .show()
        }
    }

    override fun onResume() {
        super.onResume()
        loadTree()
    }

    private fun loadTree() {
        lifecycleScope.launch {
            val tree = withContext(Dispatchers.IO) { repo.buildTree() }
            binding.mindMap.setTree(tree)
        }
    }
}
