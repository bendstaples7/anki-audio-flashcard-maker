# Design Document: Waveform Edge Dragging Bug Fix

## Overview

This document outlines the investigation and fix for the broken waveform edge dragging functionality in the manual audio alignment interface. The bug prevents users from interactively adjusting audio boundaries by dragging region edges, forcing them to use manual time entry instead. The root cause analysis focuses on WaveSurfer.js Regions plugin configuration, event listener attachment, CSS interference, and JavaScript runtime errors. The solution involves verifying plugin initialization, ensuring event handlers are properly attached, and testing across browsers to restore the drag-and-drop boundary adjustment workflow.

## Root Cause Analysis

### Investigation Findings

Based on code examination of `cantonese_anki_generator/web/static/js/app.js`, several potential issues have been identified:

#### 1. WaveSurfer.js Regions Plugin Configuration

**Current Implementation (Line 1093-1127):**
```javascript
function initializeTermWaveform(containerId, termId, options = {}) {
    const wavesurfer = WaveSurfer.create({
        container: `#${containerId}`,
        waveColor: '#95a5a6',
        progressColor: '#3498db',
        // ... other options
    });
    
    // Add regions plugin
    const regionsPlugin = wavesurfer.registerPlugin(WaveSurfer.Regions.create());
    
    // Store reference
    WaveSurferInstances.termWaveforms.set(termId, {
        instance: wavesurfer,
        regions: regionsPlugin
    });
    
    return wavesurfer;
}
```

**Region Creation (Line 1398-1408):**
```javascript
const region = waveformData.regions.addRegion({
    id: `region-${termId}`,
    start: 0,
    end: duration,
    color: 'rgba(52, 152, 219, 0.3)',
    drag: false,      // Don't allow dragging the whole region
    resize: true,     // Allow resizing from edges ✓
    content: ''
});
```

**Analysis:** The `resize: true` configuration is present, which should enable edge dragging. However, the Regions plugin may require additional configuration or the plugin instance may not be fully initialized when regions are added.

#### 2. Event Listener Setup

**Current Implementation (Line 1428-1502):**
```javascript
function setupRegionDragHandlersForTrim(termId, regionsPlugin) {
    // Listen for region update start
    regionsPlugin.on('region-update-start', (region) => {
        if (region.id === `region-${termId}`) {
            userIsDragging = true;
        }
    });
    
    // Listen for region updated
    regionsPlugin.on('region-updated', (region) => {
        // Update input fields during drag
    });
    
    // Listen for region update end
    regionsPlugin.on('region-update-end', async (region) => {
        // Trigger trim operation
    });
}
```

**Analysis:** Event listeners are attached to the regions plugin, but there's no verification that:
- The plugin is ready to receive events
- The region elements have been rendered in the DOM
- The event names match the current WaveSurfer.js version API

#### 3. Timing Issues

**Potential Race Condition:**
The region is created immediately after loading audio:
```javascript
await wavesurfer.load(audioUrl);
const duration = wavesurfer.getDuration();
const region = waveformData.regions.addRegion({...});
setupRegionDragHandlersForTrim(termId, waveformData.regions);
```

**Analysis:** If the waveform hasn't fully rendered when the region is added, the drag handles may not be properly initialized. WaveSurfer.js may need a 'ready' event before regions can be interactive.

#### 4. CSS and DOM Issues

**Waveform Container CSS (styles.css line 540-549):**
```css
.term-waveform {
    width: 100%;
    height: 80px;
    background-color: #fafafa;
    border-radius: 4px;
    border: 1px solid #e0e0e0;
    overflow: hidden;  /* May clip drag handles */
    position: relative;
}
```

**Analysis:** The `overflow: hidden` property may be clipping the region drag handles, making them inaccessible to mouse events. Additionally, there's no explicit CSS for region handles to ensure they're visible and interactive.

#### 5. WaveSurfer.js Version Compatibility

**Potential Issue:** The code uses WaveSurfer v7 API (`WaveSurfer.Regions.create()`), but if the library version changed, the Regions plugin API may have breaking changes:
- Event names may have changed
- Region configuration options may have changed
- Plugin initialization may require different parameters

### Most Likely Root Causes

1. **Missing 'ready' event wait:** Regions are added before WaveSurfer is fully ready
2. **CSS overflow clipping:** Drag handles are hidden by `overflow: hidden`
3. **Event listener timing:** Handlers attached before region elements exist in DOM
4. **WaveSurfer version mismatch:** API changes in Regions plugin

## Architecture

### Component Interaction Flow

```
User Interaction
    ↓
Region Drag Handle (DOM Element)
    ↓
WaveSurfer Regions Plugin (Event Emitter)
    ↓
setupRegionDragHandlersForTrim (Event Handlers)
    ↓
Update Input Fields + Trigger Trim
    ↓
Backend API (Save Boundaries)
```

### Key Components

1. **WaveSurfer Instance:** Core waveform rendering engine
2. **Regions Plugin:** Provides draggable region functionality
3. **Region Object:** Individual draggable region with handles
4. **Event Handlers:** JavaScript functions responding to drag events
5. **DOM Elements:** Visual representation of regions and handles

## Solution Design

### Fix Strategy

The fix will address all potential root causes through a multi-layered approach:

#### 1. Ensure WaveSurfer Ready State

**Problem:** Regions added before waveform is fully rendered
**Solution:** Wait for 'ready' or 'decode' event before adding regions

```javascript
async function renderTermWaveform(termId, audioUrl) {
    const wavesurfer = initializeTermWaveform(containerId, termId);
    
    // Load audio and wait for ready
    await new Promise((resolve) => {
        wavesurfer.once('ready', resolve);
        wavesurfer.load(audioUrl);
    });
    
    // Now add region after waveform is ready
    const waveformData = getTermWaveform(termId);
    if (waveformData && waveformData.regions) {
        const duration = wavesurfer.getDuration();
        const region = waveformData.regions.addRegion({...});
        setupRegionDragHandlersForTrim(termId, waveformData.regions);
    }
}
```

#### 2. Fix CSS Overflow Issue

**Problem:** `overflow: hidden` may clip drag handles
**Solution:** Change to `overflow: visible` or add explicit handle styling

```css
.term-waveform {
    width: 100%;
    height: 80px;
    background-color: #fafafa;
    border-radius: 4px;
    border: 1px solid #e0e0e0;
    overflow: visible; /* Allow handles to extend beyond container */
    position: relative;
}

/* Ensure region handles are visible and interactive */
.term-waveform [data-resize] {
    cursor: ew-resize !important;
    pointer-events: auto !important;
    z-index: 10 !important;
}
```

#### 3. Verify Regions Plugin Configuration

**Problem:** Plugin may need additional configuration
**Solution:** Add explicit configuration when creating plugin

```javascript
function initializeTermWaveform(containerId, termId, options = {}) {
    const wavesurfer = WaveSurfer.create({...});
    
    // Create regions plugin with explicit configuration
    const regionsPlugin = wavesurfer.registerPlugin(
        WaveSurfer.Regions.create({
            dragSelection: false,  // Disable creating regions by dragging
            // Ensure resize is enabled globally
        })
    );
    
    WaveSurferInstances.termWaveforms.set(termId, {
        instance: wavesurfer,
        regions: regionsPlugin
    });
    
    return wavesurfer;
}
```

#### 4. Add Debugging and Verification

**Problem:** No visibility into what's failing
**Solution:** Add console logging and verification checks

```javascript
function setupRegionDragHandlersForTrim(termId, regionsPlugin) {
    console.log(`Setting up trim drag handlers for term ${termId}`);
    
    // Verify plugin is ready
    if (!regionsPlugin) {
        console.error(`Regions plugin not found for term ${termId}`);
        return;
    }
    
    // Verify region exists
    const region = regionsPlugin.getRegions().find(r => r.id === `region-${termId}`);
    if (!region) {
        console.error(`Region not found for term ${termId}`);
        return;
    }
    
    console.log(`Region found:`, region);
    console.log(`Region resize enabled:`, region.resize);
    
    // Attach event listeners with logging
    regionsPlugin.on('region-update-start', (region) => {
        console.log('Drag started:', region.id);
        if (region.id === `region-${termId}`) {
            userIsDragging = true;
        }
    });
    
    // ... rest of handlers
}
```

#### 5. Verify WaveSurfer Version and API

**Problem:** API may have changed between versions
**Solution:** Check WaveSurfer version and update API calls if needed

```javascript
// Add version check
console.log('WaveSurfer version:', WaveSurfer.VERSION);

// Verify Regions plugin API
if (!WaveSurfer.Regions) {
    console.error('WaveSurfer Regions plugin not available');
}
```

### Implementation Order

1. **Add debugging logs** to understand current behavior
2. **Fix CSS overflow** issue (quick win)
3. **Add ready event wait** before region creation
4. **Verify plugin configuration** and API compatibility
5. **Test across browsers** to ensure consistency
6. **Add visual feedback** for drag handles (cursor changes)

## Components and Interfaces

### Modified Functions

#### `renderTermWaveform(termId, audioUrl)`
**Changes:**
- Add await for WaveSurfer 'ready' event before adding regions
- Add error handling for failed region creation
- Add verification that region was created successfully

#### `initializeTermWaveform(containerId, termId, options)`
**Changes:**
- Add explicit Regions plugin configuration
- Add version logging for debugging
- Return both wavesurfer instance and ready promise

#### `setupRegionDragHandlersForTrim(termId, regionsPlugin)`
**Changes:**
- Add verification that plugin and region exist
- Add console logging for debugging
- Add fallback error handling if events don't fire

### New Helper Functions

#### `verifyRegionInteractivity(termId)`
**Purpose:** Verify that a region's drag handles are interactive
**Implementation:**
```javascript
function verifyRegionInteractivity(termId) {
    const waveformData = getTermWaveform(termId);
    if (!waveformData || !waveformData.regions) {
        console.error(`No waveform data for term ${termId}`);
        return false;
    }
    
    const regions = waveformData.regions.getRegions();
    const region = regions.find(r => r.id === `region-${termId}`);
    
    if (!region) {
        console.error(`No region found for term ${termId}`);
        return false;
    }
    
    console.log(`Region ${termId} - resize enabled:`, region.resize);
    console.log(`Region ${termId} - drag enabled:`, region.drag);
    
    // Check if region element exists in DOM
    const regionElement = document.querySelector(`[data-id="region-${termId}"]`);
    if (!regionElement) {
        console.error(`Region element not found in DOM for term ${termId}`);
        return false;
    }
    
    // Check if handles exist
    const handles = regionElement.querySelectorAll('[data-resize]');
    console.log(`Region ${termId} - handles found:`, handles.length);
    
    return handles.length > 0;
}
```

#### `ensureRegionHandlesVisible(termId)`
**Purpose:** Ensure region drag handles are visible and interactive
**Implementation:**
```javascript
function ensureRegionHandlesVisible(termId) {
    const regionElement = document.querySelector(`[data-id="region-${termId}"]`);
    if (!regionElement) return;
    
    const handles = regionElement.querySelectorAll('[data-resize]');
    handles.forEach(handle => {
        handle.style.cursor = 'ew-resize';
        handle.style.pointerEvents = 'auto';
        handle.style.zIndex = '10';
    });
}
```

## Data Models

No new data models required. Existing models remain unchanged:

- `TermAlignment`: Stores boundary times
- `BoundaryUpdate`: Records user adjustments
- `AlignmentSession`: Manages session state

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Region resize configuration
*For any* term waveform with a region, the region should have `resize: true` configured
**Validates: Requirements 1.1, 1.2, 1.3**

### Property 2: Drag handle visibility
*For any* rendered region, drag handles should be present in the DOM and have appropriate cursor styling
**Validates: Requirements 1.1**

### Property 3: Event listener attachment
*For any* region created, the region-update-start, region-updated, and region-update-end event listeners should be attached to the regions plugin
**Validates: Requirements 1.2, 1.3, 1.4**

### Property 4: Real-time boundary updates
*For any* drag operation on a region edge, the time input fields should update in real-time to reflect the current boundary position
**Validates: Requirements 1.5**

### Property 5: Automatic trim on drag release
*For any* completed drag operation, the trim operation should be automatically triggered without requiring a button click
**Validates: Requirements 1.4**

### Property 6: Boundary constraint enforcement
*For any* drag operation, the dragged boundary should not cross the opposite boundary of the same region
**Validates: Requirements 2.1**

### Property 7: Adjacent term non-overlap
*For any* drag operation, the dragged boundary should not overlap with adjacent term boundaries
**Validates: Requirements 2.2**

### Property 8: Visual constraint feedback
*For any* drag operation that reaches a constraint limit, visual feedback should indicate the constraint
**Validates: Requirements 2.3**

### Property 9: Constraint limit enforcement
*For any* drag operation beyond valid limits, the boundary should stop at the constraint limit
**Validates: Requirements 2.4**

### Property 10: Invalid position reversion
*For any* drag released at an invalid position, the boundary should revert to the last valid position
**Validates: Requirements 2.5**

### Property 11: Manual entry preservation
*For any* restored drag functionality, manual time entry should continue to work identically to before
**Validates: Requirements 3.1, 3.2**

### Property 12: Interaction method consistency
*For any* boundary adjustment (drag or manual), the system should apply the same validation rules and visual feedback
**Validates: Requirements 3.3, 3.4, 3.5**

### Property 13: Cross-browser drag functionality
*For any* modern browser (Chrome, Firefox, Safari, Edge), edge dragging should work consistently
**Validates: Requirements 4.1**

### Property 14: Touch input support
*For any* tablet device with touch input, edge dragging should respond to touch drag gestures
**Validates: Requirements 4.3**

### Property 15: Cursor feedback consistency
*For any* supported platform, appropriate cursor feedback should be provided when hovering over drag handles
**Validates: Requirements 4.5**

## Error Handling

### Error Scenarios and Handling

#### 1. WaveSurfer Not Ready
**Scenario:** Region added before waveform is ready
**Detection:** Check for 'ready' event completion
**Handling:** Wait for ready event before adding region
**User Impact:** None (handled automatically)

#### 2. Regions Plugin Not Initialized
**Scenario:** Plugin not properly registered
**Detection:** Check if `regionsPlugin` is null/undefined
**Handling:** Log error, attempt to reinitialize, show user message
**User Impact:** Drag functionality unavailable, fallback to manual entry

#### 3. Region Creation Failed
**Scenario:** `addRegion()` returns null or throws error
**Detection:** Check return value and catch exceptions
**Handling:** Log error, retry once, show user message if retry fails
**User Impact:** Drag functionality unavailable for that term

#### 4. Event Listeners Not Firing
**Scenario:** Drag events don't trigger handlers
**Detection:** Add timeout check after drag should have started
**Handling:** Log warning, suggest browser refresh
**User Impact:** Drag appears to work but doesn't update boundaries

#### 5. CSS Blocking Interaction
**Scenario:** Drag handles not clickable due to CSS
**Detection:** Check computed styles for pointer-events
**Handling:** Override CSS with inline styles or !important rules
**User Impact:** None (handled automatically)

### Error Recovery Strategy

1. **Automatic Retry:** Attempt to reinitialize regions once if creation fails
2. **Graceful Degradation:** Fall back to manual time entry if drag fails
3. **User Notification:** Show clear message if drag functionality unavailable
4. **Debug Information:** Log detailed error info to console for troubleshooting

## Testing Strategy

### Manual Testing Checklist

1. **Basic Drag Functionality**
   - [ ] Hover over left edge shows resize cursor
   - [ ] Hover over right edge shows resize cursor
   - [ ] Drag left edge moves start boundary
   - [ ] Drag right edge moves end boundary
   - [ ] Release triggers automatic trim

2. **Real-time Updates**
   - [ ] Time input fields update during drag
   - [ ] Waveform region updates during drag
   - [ ] Visual feedback shows valid/invalid positions

3. **Constraints**
   - [ ] Cannot drag start past end
   - [ ] Cannot drag end before start
   - [ ] Cannot overlap adjacent terms
   - [ ] Visual feedback at constraint limits

4. **Browser Compatibility**
   - [ ] Works in Chrome
   - [ ] Works in Firefox
   - [ ] Works in Safari
   - [ ] Works in Edge
   - [ ] Works on tablet with touch

5. **Integration**
   - [ ] Manual time entry still works
   - [ ] Both methods produce same results
   - [ ] Saved boundaries persist correctly

### Automated Testing

#### Unit Tests

**Test: Region Configuration**
```javascript
test('region should be created with resize enabled', () => {
    const region = createTestRegion();
    expect(region.resize).toBe(true);
    expect(region.drag).toBe(false);
});
```

**Test: Event Listener Attachment**
```javascript
test('drag event listeners should be attached', () => {
    const mockPlugin = createMockRegionsPlugin();
    setupRegionDragHandlersForTrim('test-term', mockPlugin);
    
    expect(mockPlugin.on).toHaveBeenCalledWith('region-update-start', expect.any(Function));
    expect(mockPlugin.on).toHaveBeenCalledWith('region-updated', expect.any(Function));
    expect(mockPlugin.on).toHaveBeenCalledWith('region-update-end', expect.any(Function));
});
```

**Test: Boundary Validation**
```javascript
test('drag should not allow start to exceed end', () => {
    const region = createTestRegion({ start: 1.0, end: 2.0 });
    const result = validateDragBoundary(region, 'start', 2.5);
    
    expect(result.valid).toBe(false);
    expect(result.constrainedValue).toBe(2.0);
});
```

#### Integration Tests

**Test: End-to-End Drag Operation**
```javascript
test('dragging edge should update boundaries and trigger trim', async () => {
    const termId = 'test-term';
    await renderTermWaveform(termId, 'test-audio.mp3');
    
    // Simulate drag
    const region = getRegion(termId);
    simulateDrag(region, 'end', 2.5);
    
    // Verify updates
    const endInput = document.getElementById(`end-${termId}`);
    expect(endInput.value).toBe('2.50');
    
    // Verify trim was called
    expect(mockTrimFunction).toHaveBeenCalledWith(termId);
});
```

### Property-Based Tests

**Property Test: Drag Constraints**
```javascript
// Feature: waveform-drag-fix, Property 6: Boundary constraint enforcement
test('property: dragged boundary never crosses opposite boundary', () => {
    fc.assert(
        fc.property(
            fc.float({ min: 0, max: 10 }), // start
            fc.float({ min: 0, max: 10 }), // end
            fc.float({ min: 0, max: 10 }), // new position
            (start, end, newPos) => {
                fc.pre(start < end); // Ensure valid initial state
                
                const region = createTestRegion({ start, end });
                
                // Try to drag start boundary
                const result = validateDragBoundary(region, 'start', newPos);
                expect(result.constrainedValue).toBeLessThan(end);
                
                // Try to drag end boundary
                const result2 = validateDragBoundary(region, 'end', newPos);
                expect(result2.constrainedValue).toBeGreaterThan(start);
            }
        ),
        { numRuns: 100 }
    );
});
```

### Testing Configuration

- **Unit tests:** Run with Jest or similar JavaScript testing framework
- **Integration tests:** Run in headless browser (Puppeteer/Playwright)
- **Property tests:** Use fast-check library for JavaScript
- **Manual tests:** Test in real browsers on different platforms
- **Minimum 100 iterations** for each property-based test

## Implementation Notes

### Development Workflow

1. **Add debugging first:** Insert console.log statements to understand current behavior
2. **Test in isolation:** Create minimal HTML page with just WaveSurfer to verify library works
3. **Fix incrementally:** Apply one fix at a time and test
4. **Verify in browser:** Use browser DevTools to inspect DOM and event listeners
5. **Test across browsers:** Verify fix works in all supported browsers

### Rollback Plan

If the fix introduces new issues:
1. Revert CSS changes first (least risky)
2. Revert JavaScript changes to event handling
3. Revert to previous WaveSurfer version if needed
4. Document any breaking changes discovered

### Performance Considerations

- Event listeners should be attached once per region, not repeatedly
- Avoid excessive DOM queries during drag (cache element references)
- Throttle real-time updates if performance issues occur
- Clean up event listeners when regions are destroyed

## Success Metrics

The fix is successful when:

1. **Functional:** Edge dragging works for all terms in all supported browsers
2. **Reliable:** No JavaScript errors in console during drag operations
3. **Performant:** Drag updates are smooth with no lag
4. **Compatible:** Manual time entry continues to work as before
5. **Tested:** All automated tests pass and manual testing checklist complete
