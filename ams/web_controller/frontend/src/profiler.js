import './app.css'
import Profiler from './Profiler.svelte'

const app = new Profiler({
  target: document.getElementById('app'),
})

export default app
