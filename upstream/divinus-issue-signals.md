# Issue → OpenIPC/divinus: no signal stops divinus; SIGTERM restarts it

## What happens

`main.c` installs `handle_exit` for SIGHUP, SIGINT, SIGQUIT and SIGTERM. It sets
`graceful = 1`, and after the main loop `if (graceful) execvp(argv[0], argv)`: every
catchable termination signal re-executes divinus with the same PID. Observed on SSC323:
after `kill -INT` / `kill -TERM` the log shows `Graceful shutdown...` followed by a new
`[media] SDK has started successfully!`, and `pidof divinus` keeps returning the PID.

The only way to stop it is SIGKILL, which skips `sdk_stop()` and the rest of the
cleanup. That makes it hard to supervise from an init script (stop/restart) or to hand
the pipeline over to another process.

## Suggestion

Keep SIGHUP as "reload/restart" and let SIGTERM/SIGINT/SIGQUIT run the same cleanup
and then exit, the usual daemon convention.
