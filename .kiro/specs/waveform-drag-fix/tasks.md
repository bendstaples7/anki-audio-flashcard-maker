# Implementation Plan: Waveform Edge Dragging Bug Fix

## Overview

This plan outlines the steps to diagnose and fix the broken waveform edge dragging functionality. The approach follows a systematic debugging process: first adding instrumentation to understand the current behavior, then applying targeted fixes based on the root cause analysis, and finally verifying the fix works across all supported browsers.

## Tasks

- [x] 1. Add debugging instrumentation to understand current behavior
  - Add console logging to track WaveSurfer initialization lifecycle
  - Add logging to verify Regions plugin registration
  - Add logging to track region creation and configuration
  - Add logging to verify event listener attachment
  - Add logging to track drag events (start, update, end)
  - Add DOM inspection to verify drag handle elements exist
  - Test in browser and review console output to identify failure point
  - _Requirements: Investigation, All Requirements_

- [x] 2. Fix CSS overflow issue that may clip drag handles
  - [x] 2.1 Update term-waveform CSS to allow handles to be visible
    - Change `overflow: hidden` to `overflow: visible` in `.term-waveform` class
    - Test that waveform container still looks correct
    - _Requirements: 1.1_
  
  - [x] 2.2 Add explicit CSS for region drag handles
    - Add CSS rules for `[data-resize]` elements to ensure visibility
    - Set `cursor: ew-resize` for resize handles
    - Set `pointer-events: auto` to ensure handles are interactive
    - Set appropriate `z-index` to ensure handles are on top
    - _Requirements: 1.1, 4.5_
  
  - [x] 2.3 Test CSS changes in browser
    - Verify drag handles are visible
    - Verify cursor changes on hover
    - Verify handles are clickable
    - _Requirements: 1.1, 4.5_

- [x] 3. Fix WaveSurfer ready state timing issue
  - [x] 3.1 Update renderTermWaveform to wait for ready event
    - Wrap wavesurfer.load() in Promise that resolves on 'ready' event
    - Use `wavesurfer.once('ready', resolve)` before loading audio
    - Ensure region is only added after ready event fires
    - _Requirements: 1.2, 1.3_
  
  - [x] 3.2 Add error handling for load failures
    - Catch errors during audio loading
    - Log errors and show user-friendly message
    - Provide retry option if load fails
    - _Requirements: 1.2, 1.3_
  
  - [ ]* 3.3 Write unit test for ready event timing
    - Test that region is not added before ready event
    - Test that region is added after ready event
    - _Requirements: 1.2, 1.3_

- [x] 4. Verify and enhance Regions plugin configuration
  - [x] 4.1 Add explicit configuration when creating Regions plugin
    - Pass configuration object to `WaveSurfer.Regions.create()`
    - Set `dragSelection: false` to prevent accidental region creation
    - Add any other required configuration options
    - _Requirements: 1.2, 1.3_
  
  - [x] 4.2 Add WaveSurfer version logging
    - Log `WaveSurfer.VERSION` on initialization
    - Verify version matches expected version
    - Document any version-specific API differences
    - _Requirements: 4.1_
  
  - [x] 4.3 Verify region configuration after creation
    - Log region properties after `addRegion()` call
    - Verify `resize: true` is set correctly
    - Verify `drag: false` is set correctly
    - _Requirements: 1.2, 1.3_

- [x] 5. Enhance event listener setup with verification
  - [x] 5.1 Add verification checks in setupRegionDragHandlersForTrim
    - Check that regionsPlugin is not null/undefined
    - Check that region exists using `getRegions()`
    - Log warning if region not found
    - Return early if verification fails
    - _Requirements: 1.4_
  
  - [x] 5.2 Add event listener verification
    - Log when each event listener is attached
    - Add test event to verify listeners are firing
    - Log when drag events fire (start, update, end)
    - _Requirements: 1.4, 1.5_
  
  - [ ]* 5.3 Write unit test for event listener attachment
    - Mock regions plugin
    - Verify all three event listeners are attached
    - Verify event handlers are called with correct parameters
    - _Requirements: 1.4_

- [x] 6. Implement helper functions for verification
  - [x] 6.1 Create verifyRegionInteractivity function
    - Check that waveform data exists
    - Check that region exists in regions list
    - Check that region element exists in DOM
    - Check that drag handles exist in DOM
    - Return boolean indicating if region is interactive
    - _Requirements: 1.1, 1.2, 1.3_
  
  - [x] 6.2 Create ensureRegionHandlesVisible function
    - Find region element in DOM
    - Find all drag handle elements
    - Apply inline styles to ensure visibility and interactivity
    - Set cursor, pointer-events, and z-index
    - _Requirements: 1.1, 4.5_
  
  - [x] 6.3 Call helper functions after region creation
    - Call verifyRegionInteractivity after setupRegionDragHandlersForTrim
    - Call ensureRegionHandlesVisible if verification passes
    - Log results for debugging
    - _Requirements: 1.1, 1.2, 1.3_

- [x] 7. Test drag functionality in development environment
  - Load manual alignment interface with test data
  - Verify console logs show correct initialization sequence
  - Test hovering over region edges (cursor should change)
  - Test dragging left edge (start boundary should move)
  - Test dragging right edge (end boundary should move)
  - Verify time input fields update during drag
  - Verify trim is triggered automatically on drag release
  - Test with multiple terms to ensure consistency
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [-] 8. Test boundary constraints
  - [x] 8.1 Test start boundary cannot exceed end boundary
    - Drag start boundary past end boundary
    - Verify boundary stops at constraint limit
    - Verify visual feedback is provided
    - _Requirements: 2.1, 2.3, 2.4_
  
  - [ ] 8.2 Test end boundary cannot precede start boundary
    - Drag end boundary before start boundary
    - Verify boundary stops at constraint limit
    - Verify visual feedback is provided
    - _Requirements: 2.1, 2.3, 2.4_
  
  - [ ] 8.3 Test boundaries cannot overlap adjacent terms
    - Drag boundary toward adjacent term
    - Verify boundary stops before overlap
    - Verify visual feedback is provided
    - _Requirements: 2.2, 2.3, 2.4_
  
  - [ ]* 8.4 Write property test for boundary constraints
    - **Property 6: Boundary constraint enforcement**
    - **Validates: Requirements 2.1**
    - Generate random start/end times and drag positions
    - Verify dragged boundary never crosses opposite boundary
    - Run 100+ iterations

- [ ] 9. Test manual time entry still works
  - Type new start time in input field
  - Click trim button
  - Verify boundary updates correctly
  - Type new end time in input field
  - Click trim button
  - Verify boundary updates correctly
  - Verify same validation rules apply as drag
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 10. Cross-browser compatibility testing
  - [ ] 10.1 Test in Chrome
    - Verify drag functionality works
    - Verify cursor feedback is correct
    - Verify no console errors
    - _Requirements: 4.1, 4.5_
  
  - [ ] 10.2 Test in Firefox
    - Verify drag functionality works
    - Verify cursor feedback is correct
    - Verify no console errors
    - _Requirements: 4.1, 4.5_
  
  - [ ] 10.3 Test in Safari
    - Verify drag functionality works
    - Verify cursor feedback is correct
    - Verify no console errors
    - _Requirements: 4.1, 4.5_
  
  - [ ] 10.4 Test in Edge
    - Verify drag functionality works
    - Verify cursor feedback is correct
    - Verify no console errors
    - _Requirements: 4.1, 4.5_
  
  - [ ] 10.5 Test on tablet with touch input
    - Verify touch drag gestures work
    - Verify touch feedback is appropriate
    - Test on iPad or Android tablet
    - _Requirements: 4.3_

- [ ] 11. Performance and edge case testing
  - Test with session containing many terms (20+)
  - Verify drag performance is smooth with no lag
  - Test rapid dragging back and forth
  - Test dragging while audio is playing
  - Test dragging immediately after page load
  - Test dragging after zooming waveform
  - Verify no memory leaks from event listeners
  - _Requirements: 1.2, 1.3, 1.4_

- [ ] 12. Checkpoint - Verify all functionality restored
  - Ensure all tests pass, ask the user if questions arise.
  - Verify drag functionality works in all browsers
  - Verify manual time entry still works
  - Verify no regressions in other features
  - Verify no JavaScript errors in console
  - Get user confirmation that fix resolves the issue

- [ ] 13. Clean up debugging code
  - Remove or comment out excessive console.log statements
  - Keep essential error logging
  - Keep verification checks that don't impact performance
  - Update code comments to document the fix
  - _Requirements: All_

- [ ]* 14. Update documentation
  - Document the root cause of the bug
  - Document the fix applied
  - Document any WaveSurfer version requirements
  - Update troubleshooting guide if needed
  - _Requirements: All_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster resolution
- Focus on tasks 1-7 first to restore basic functionality
- Tasks 8-11 ensure robustness and compatibility
- Task 12 is a checkpoint to verify the fix before cleanup
- The debugging instrumentation in task 1 is critical for understanding the issue
- CSS fixes (task 2) are quick wins that may resolve the issue immediately
- Ready event timing (task 3) is the most likely root cause based on code analysis
