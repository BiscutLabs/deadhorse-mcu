/* size probes: nm -S on the object gives sizeof() of each type */
#include "control.h"
char probe_state[sizeof(state_t)];
char probe_params[sizeof(params_t)];
char probe_inputs[sizeof(inputs_t)];
char probe_outputs[sizeof(outputs_t)];
