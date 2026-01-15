# Manual Test Plan for Audio Playback Controls

## Task 9: Audio Playback Controls Implementation

This document describes how to manually test the audio playback controls implementation.

## Prerequisites

1. Start the Flask web server:
   ```bash
   python -m cantonese_anki_generator.web.run
   ```

2. Open a web browser and navigate to `http://localhost:3000`

## Test Cases

### Test 9.1: Playback Management System

#### Test 9.1.1: Play Button Click Handler
**Steps:**
1. Upload a vocabulary document URL and audio file
2. Wait for automatic alignment to complete
3. Locate a term row in the alignment table
4. Click the "▶ Play" button for that term

**Expected Results:**
- Audio for that specific term should start playing
- Button text should change to "⏸ Pause"
- Button should have a red background color with pulse animation
- Term row should have a light red background with pulse animation

#### Test 9.1.2: Stop Currently Playing Audio
**Steps:**
1. Click "▶ Play" on term 1
2. While term 1 is playing, click "▶ Play" on term 2

**Expected Results:**
- Term 1 audio should stop immediately
- Term 1 button should return to "▶ Play" state
- Term 1 row background should return to normal
- Term 2 audio should start playing
- Term 2 button should show "⏸ Pause" state
- Term 2 row should have playing animation

#### Test 9.1.3: Pause and Resume
**Steps:**
1. Click "▶ Play" on a term
2. While playing, click "⏸ Pause"
3. Click "▶ Play" again

**Expected Results:**
- First click: Audio starts playing
- Second click: Audio pauses, button shows "▶ Play"
- Third click: Audio resumes from where it paused

### Test 9.2: Playback State Visualization

#### Test 9.2.1: Active Playback Indicator
**Steps:**
1. Click "▶ Play" on any term
2. Observe the button and term row

**Expected Results:**
- Play button should:
  - Change text to "⏸ Pause"
  - Change background color to red (#e74c3c)
  - Show a pulsing animation (shadow expanding and fading)
- Term row should:
  - Change background color to light red (#fff5f5)
  - Show a pulsing animation (background color alternating)
  - Show a red left border (4px solid #e74c3c)

#### Test 9.2.2: Return to Ready State on Completion
**Steps:**
1. Click "▶ Play" on a short term
2. Wait for the audio to finish playing completely

**Expected Results:**
- When audio completes:
  - Button text should change back to "▶ Play"
  - Button background should return to blue (#3498db)
  - Pulse animation should stop
  - Term row background should return to normal
  - Red left border should disappear

#### Test 9.2.3: Button State During Playback
**Steps:**
1. Click "▶ Play" on term 1
2. Observe button states for all terms

**Expected Results:**
- Playing term button: Red with "⏸ Pause" and pulse animation
- All other term buttons: Blue with "▶ Play" and no animation

#### Test 9.2.4: Multiple Play/Pause Cycles
**Steps:**
1. Click "▶ Play" on term 1
2. Click "⏸ Pause"
3. Click "▶ Play" on term 2
4. Click "⏸ Pause"
5. Click "▶ Play" on term 1 again

**Expected Results:**
- Each play action should show proper visual feedback
- Each pause action should remove visual feedback
- Switching between terms should properly update all visual states
- No visual artifacts or stuck states

## Error Handling Tests

### Test 9.3: Error Scenarios

#### Test 9.3.1: Audio Load Failure
**Steps:**
1. Manually modify the audio_segment_url in browser console to an invalid URL
2. Try to play the term

**Expected Results:**
- Error toast should appear with message "Failed to play audio for term X"
- Button should return to ready state
- Console should log the error

#### Test 9.3.2: Missing Waveform
**Steps:**
1. In browser console, call `playTermAudio('nonexistent_term')`

**Expected Results:**
- Error toast should appear with message "Audio not loaded for this term"
- Console should log error message
- No visual state changes

## Browser Compatibility

Test the above scenarios in:
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (if available)

## Performance Tests

### Test 9.4: Rapid Clicking
**Steps:**
1. Rapidly click play buttons on different terms (5-10 clicks in quick succession)

**Expected Results:**
- Only the last clicked term should be playing
- All previous terms should be stopped
- No audio overlap or glitches
- Visual states should be correct for all terms

### Test 9.5: Long Audio Files
**Steps:**
1. Test with audio file containing 20+ terms
2. Play various terms throughout the list

**Expected Results:**
- Playback should work smoothly for all terms
- Visual feedback should be consistent
- No performance degradation

## Accessibility Tests

### Test 9.6: Keyboard Navigation
**Steps:**
1. Use Tab key to navigate to play buttons
2. Press Enter/Space to activate buttons

**Expected Results:**
- Buttons should be keyboard accessible
- Visual focus indicators should be visible
- Playback should work via keyboard

## Notes

- All visual animations should be smooth (no jank)
- State transitions should be immediate (no delay)
- Audio playback should be isolated (only one term playing at a time)
- Error messages should be user-friendly and actionable

## Test Results

Date: ___________
Tester: ___________

| Test Case | Pass/Fail | Notes |
|-----------|-----------|-------|
| 9.1.1 | | |
| 9.1.2 | | |
| 9.1.3 | | |
| 9.2.1 | | |
| 9.2.2 | | |
| 9.2.3 | | |
| 9.2.4 | | |
| 9.3.1 | | |
| 9.3.2 | | |
| 9.4 | | |
| 9.5 | | |
| 9.6 | | |
