Things to add to web interface and ams:
- upgrade in-game launch interstitial, hide options under collapser, make options reasonable ui elements based on type -- dropdowns, sliders, ...
- ability to tune parameters (initially for pacing) on the fly (sliders or up/down arrows)
- pygame-wasm observer mode (+ video stream from detection camera?)
- test mode (place object in front of screen, show detection cycle -- uses gradient calibration game)

advanced:
- px to physical size calculation (measure projected size, input to webui)
- minutes of arc calculation (once size measured, enter rangefinder distance)
- "watch mode" on ipad/laptop in web -- use pygame-wasm to watch stream of events on local screen

for all games with levels:
- level groups instead of individual levels per game (progress through challenges)
- upgrade all games to use temporal game state at the core, to close the loop on CV latency mitigation
- level editor/author ui (start with simple yaml editor + pygame-wasm in mouse mode to test - saves into a "user data" folder, which can be propagated into game library or overlaid on the local system -- allows for downloading levels from marketplace into personal library as well as writing your own)
