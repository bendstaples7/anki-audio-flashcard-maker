# Task 9: Audio Playback Control Flow

## Playback State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                    PLAYBACK STATE MACHINE                    │
└─────────────────────────────────────────────────────────────┘

                    ┌──────────┐
                    │  READY   │
                    │  State   │
                    └────┬─────┘
                         │
                         │ User clicks "▶ Play"
                         │
                         ▼
                    ┌──────────┐
              ┌────▶│ PLAYING  │────┐
              │     │  State   │    │
              │     └────┬─────┘    │
              │          │          │
              │          │          │ User clicks "⏸ Pause"
              │          │          │
              │          │          ▼
              │          │     ┌──────────┐
              │          │     │  PAUSED  │
              │          │     │  State   │
              │          │     └────┬─────┘
              │          │          │
              │          │          │ User clicks "▶ Play"
              │          │          │
              │          └──────────┘
              │
              │ Audio finishes OR
              │ User plays different term OR
              │ Error occurs
              │
              └──────────────────────────────────────┐
                                                     │
                                                     ▼
                                              ┌──────────┐
                                              │  READY   │
                                              │  State   │
                                              └──────────┘
```

## Function Call Flow

### Scenario 1: User Plays a Term

```
User clicks "▶ Play" button
         │
         ▼
playTermAudio(termId)
         │
         ├─→ Check if waveform exists
         │   └─→ If not: Show error, return
         │
         ├─→ Check if another term is playing
         │   └─→ If yes: stopTermAudio(currentlyPlaying)
         │                    │
         │                    ├─→ wavesurfer.pause()
         │                    ├─→ wavesurfer.seekTo(0)
         │                    └─→ updatePlaybackState(termId, 'ready')
         │
         ├─→ Check if current term is playing
         │   ├─→ If yes: wavesurfer.pause()
         │   │           updatePlaybackState(termId, 'ready')
         │   │
         │   └─→ If no: wavesurfer.play()
         │               updatePlaybackState(termId, 'playing')
         │               Set up event listeners:
         │                    │
         │                    ├─→ on 'finish':
         │                    │   updatePlaybackState(termId, 'ready')
         │                    │   AppState.currentlyPlaying = null
         │                    │
         │                    └─→ on 'error':
         │                        updatePlaybackState(termId, 'ready')
         │                        AppState.currentlyPlaying = null
         │                        showError(message)
         │
         └─→ Return
```

### Scenario 2: Update Playback State

```
updatePlaybackState(termId, state)
         │
         ├─→ Get button and row elements
         │   └─→ If not found: return
         │
         ├─→ Remove all state classes
         │
         ├─→ Switch on state:
         │   │
         │   ├─→ 'playing':
         │   │   ├─→ Button: "⏸ Pause", red, .playing class
         │   │   ├─→ Row: .playing-audio class
         │   │   └─→ AppState.currentlyPlaying = termId
         │   │
         │   ├─→ 'paused':
         │   │   ├─→ Button: "▶ Play", orange, .paused class
         │   │   └─→ Keep currentlyPlaying set
         │   │
         │   └─→ 'ready':
         │       ├─→ Button: "▶ Play", blue, .ready class
         │       ├─→ Row: normal styling
         │       └─→ Clear currentlyPlaying if matches termId
         │
         └─→ Return
```

## Visual State Indicators

### Button States

```
┌─────────────────────────────────────────────────────────────┐
│                      BUTTON STATES                           │
└─────────────────────────────────────────────────────────────┘

READY State:
┌──────────────────┐
│  ▶ Play          │  Blue background (#3498db)
│                  │  No animation
└──────────────────┘

PLAYING State:
┌──────────────────┐
│  ⏸ Pause         │  Red background (#e74c3c)
│  ◉ ◉ ◉          │  Pulse animation (expanding shadow)
└──────────────────┘

PAUSED State:
┌──────────────────┐
│  ▶ Play          │  Orange background (#f39c12)
│                  │  No animation
└──────────────────┘
```

### Row States

```
┌─────────────────────────────────────────────────────────────┐
│                       ROW STATES                             │
└─────────────────────────────────────────────────────────────┘

NORMAL (Ready):
┌────────────────────────────────────────────────────────────┐
│ Term Info │ Waveform │ Controls │ Quality                  │
│           │          │          │                          │
└────────────────────────────────────────────────────────────┘
White background, no border

PLAYING:
┃┌───────────────────────────────────────────────────────────┐
┃│ Term Info │ Waveform │ Controls │ Quality                 │
┃│           │          │          │                         │
┃└───────────────────────────────────────────────────────────┘
Red left border (4px), light red background (#fff5f5)
Pulsing animation (background alternates)
```

## CSS Animations

### Pulse Animation (Button)

```css
@keyframes pulse {
    0%, 100% {
        box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7);
    }
    50% {
        box-shadow: 0 0 0 8px rgba(231, 76, 60, 0);
    }
}
```

Effect: Expanding shadow that fades out, creating a pulsing effect

### Highlight Pulse Animation (Row)

```css
@keyframes highlightPulse {
    0%, 100% {
        background-color: #fff5f5;
    }
    50% {
        background-color: #ffe5e5;
    }
}
```

Effect: Background color alternates between light red shades

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA FLOW                               │
└─────────────────────────────────────────────────────────────┘

AppState
    │
    ├─→ currentlyPlaying: string | null
    │   └─→ Tracks which term is currently playing
    │
    └─→ alignments: Array<TermAlignment>
        └─→ Contains all term data including audio URLs

WaveSurferInstances
    │
    └─→ termWaveforms: Map<termId, {instance, regions}>
        └─→ Stores WaveSurfer instances for each term

DOM Elements
    │
    ├─→ Play buttons: .play-btn[data-term-id="..."]
    │   └─→ Click handlers trigger playTermAudio()
    │
    └─→ Term rows: #term-row-{termId}
        └─→ Visual feedback during playback
```

## Error Handling Flow

```
Error Occurs
    │
    ├─→ Missing waveform data
    │   └─→ showError("Audio not loaded for this term")
    │       console.error(...)
    │       return early
    │
    ├─→ Playback error (WaveSurfer)
    │   └─→ updatePlaybackState(termId, 'ready')
    │       AppState.currentlyPlaying = null
    │       showError("Failed to play audio for term X")
    │       console.error(...)
    │
    └─→ Missing UI elements
        └─→ console.error(...)
            return early
```

## Integration with Other Components

```
┌─────────────────────────────────────────────────────────────┐
│                    COMPONENT INTEGRATION                     │
└─────────────────────────────────────────────────────────────┘

Task 8: Waveform Rendering
    │
    ├─→ Creates WaveSurfer instances
    ├─→ Loads audio segments
    └─→ Provides getTermWaveform() function
            │
            └─→ Used by playTermAudio()

Task 3: Session Management
    │
    ├─→ Provides session data
    └─→ Includes audio_segment_url for each term
            │
            └─→ Used to load audio in WaveSurfer

Task 4: Audio Extraction
    │
    └─→ Generates audio segments
            │
            └─→ Served by API for playback

Task 10: Interactive Boundary Adjustment
    │
    └─→ **Completed**: Interactive Boundary Adjustment implemented
            │
            ├─→ Draggable boundary markers
            ├─→ Real-time waveform updates
            ├─→ Backend synchronization
            ├─→ Playback used to verify adjustments
            └─→ Play adjusted segments immediately
```

## Performance Considerations

1. **Single Playback**: Only one term plays at a time
   - Prevents audio overlap
   - Reduces memory usage
   - Improves user experience

2. **Event Cleanup**: Event listeners are properly managed
   - Uses `.once()` for finish/error events
   - Prevents memory leaks

3. **State Tracking**: Minimal state in AppState
   - Only tracks currently playing term
   - Efficient state updates

4. **DOM Updates**: Targeted updates only
   - Only updates affected elements
   - Uses CSS classes for styling
   - Smooth animations via CSS

## Accessibility

1. **Keyboard Navigation**: Buttons are keyboard accessible
2. **Visual Feedback**: Clear visual indicators for all states
3. **Error Messages**: User-friendly error messages
4. **State Persistence**: State is maintained across interactions
