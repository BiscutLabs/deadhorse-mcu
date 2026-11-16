// Port-only clock-phase model, run by pinned Icarus against unchanged PDK RTL.
#include <vpi_user.h>
#include <array>
#include <vector>
#include <string>
#include <cstdlib>

struct Stimulus { int clock, enable, test; };
static std::vector<Stimulus> sequence;
static size_t position=0;
static int captured=0;
static bool corrupt=false;
static std::array<vpiHandle,4> pins;
static unsigned transitions=0;
static void drive(vpiHandle pin,int bit) {
    s_vpi_value value{}; value.format=vpiIntVal; value.value.integer=bit;
    vpi_put_value(pin,&value,nullptr,vpiNoDelay);
}
static void schedule(PLI_INT32 (*fn)(p_cb_data),int reason,unsigned delay=0) {
    s_vpi_time time{}; time.type=vpiSimTime; time.low=delay;
    s_cb_data cb{}; cb.reason=reason; cb.cb_rtn=fn; cb.time=&time;
    vpi_register_cb(&cb);
}
static PLI_INT32 apply(p_cb_data);
static PLI_INT32 warmup(p_cb_data) {
    // Begin checking only after a complete low phase. This also gives the
    // deliberately wrong falling-edge fixture a known captured state.
    drive(pins[0],0); schedule(apply,cbAfterDelay,1); return 0;
}
static PLI_INT32 sample(p_cb_data) {
    const auto s=sequence[position];
    if(!s.clock) captured=s.enable || s.test;
    s_vpi_value value{}; value.format=vpiScalarVal; vpi_get_value(pins[3],&value);
    const int expected=s.clock ? captured : 0;
    const int actual=value.value.scalar;
    if(actual!=vpi0 && actual!=vpi1) {
        vpi_printf("FAIL CLOCK_GATE_MODEL_MISMATCH: unknown output at %u\n",transitions);
        vpi_control(vpiFinish,1); return 0;
    }
    if((actual ^ (corrupt ? 1:0))!=expected) {
        vpi_printf("FAIL CLOCK_GATE_MODEL_MISMATCH at %u: expected=%d actual=%d\n",transitions,expected,actual);
        vpi_control(vpiFinish,1); return 0;
    }
    transitions++;
    if(++position==sequence.size()) {
        vpi_printf("PASS CLOCK_GATE_PHASE_MODEL transitions=%u\n",transitions);
        vpi_control(vpiFinish,0);
    } else schedule(apply,cbAfterDelay,1);
    return 0;
}
static PLI_INT32 apply(p_cb_data) {
    const auto s=sequence[position];
    drive(pins[0],s.clock); drive(pins[1],s.enable); drive(pins[2],s.test);
    schedule(sample,cbReadOnlySynch); return 0;
}
static PLI_INT32 start(p_cb_data) {
    s_vpi_vlog_info info{}; vpi_get_vlog_info(&info);
    for(int i=0;i<info.argc;i++) if(std::string(info.argv[i])=="+corrupt") corrupt=true;
    const char* names[]={"ClockGate.clk_i","ClockGate.en_i","ClockGate.test_en_i","ClockGate.clk_o"};
    for(int i=0;i<4;i++) {
        pins[i]=vpi_handle_by_name(const_cast<char*>(names[i]),nullptr);
        if(!pins[i]) { vpi_printf("FAIL missing clock-gate port\n"); vpi_control(vpiFinish,1); return 0; }
    }
    for(int low=0;low<4;low++) for(int high=0;high<4;high++) for(int after=0;after<4;after++) {
        sequence.push_back({0,low&1,(low>>1)&1});
        sequence.push_back({0,high&1,(high>>1)&1});
        sequence.push_back({0,after&1,(after>>1)&1});
        sequence.push_back({1,after&1,(after>>1)&1});
        sequence.push_back({1,high&1,(high>>1)&1});
        sequence.push_back({1,after&1,(after>>1)&1});
        sequence.push_back({0,after&1,(after>>1)&1});
        sequence.push_back({1,after&1,(after>>1)&1});
    }
    drive(pins[1],0); drive(pins[2],0); drive(pins[0],1);
    schedule(warmup,cbAfterDelay,1); return 0;
}
static void initialize() { schedule(start,cbStartOfSimulation); }
extern "C" { void (*vlog_startup_routines[])()={initialize,nullptr}; }
