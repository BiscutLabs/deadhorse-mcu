// Port-only oracle for the mapped reset-held mux. Functional cell models only:
// no analog metastability, pulse-width or extracted-delay qualification.
#include <vpi_user.h>
#include <array>
#include <string>
static std::array<vpiHandle,13> p;
static unsigned step=0,edges=0,transitions=0;
static int external=0,bypass=0,priorClock=0,expectedClock=0;
static bool checking=false;
static void drive(int pin,int bit) {
    s_vpi_value v{};v.format=vpiIntVal;v.value.integer=bit;
    vpi_put_value(p[pin],&v,nullptr,vpiNoDelay);
}
static int read(int pin) {
    s_vpi_value v{};v.format=vpiScalarVal;vpi_get_value(p[pin],&v);
    return v.value.scalar;
}
static void schedule(PLI_INT32(*f)(p_cb_data),int reason,unsigned delay=0) {
    s_vpi_time t{};t.type=vpiSimTime;t.low=delay;
    s_cb_data cb{};cb.reason=reason;cb.cb_rtn=f;cb.time=&t;vpi_register_cb(&cb);
}
static void fail(const char* reason) {
    vpi_printf("FAIL RESET_CELL_CONTRACT step=%u reason=%s\n",step,reason);
    vpi_control(vpiFinish,1);
}
static PLI_INT32 apply(p_cb_data);
static PLI_INT32 changed(p_cb_data) {if(checking) ++transitions;return 0;}
static PLI_INT32 sample(p_cb_data) {
    const bool pinReset=step<60 || (step>=500 && step<520);
    const bool supplyReset=step<40 || (step>=300 && step<320);
    const bool reset=pinReset || (!bypass && supplyReset);
    if(reset) edges=0;
    else if(expectedClock && !priorClock) ++edges;
    if(step>2) {
        if(read(6)!=expectedClock) {fail("clock selection");return 0;}
        if(transitions>unsigned(expectedClock!=priorClock)) {fail("extra clock transition");return 0;}
        if(read(8)!=(bypass ? !pinReset : !supplyReset)) {fail("cold reset routing");return 0;}
        if(read(9)!=!pinReset) {fail("warm reset routing");return 0;}
        if((reset || edges<11) && read(7)!=0) {fail("early reset release");return 0;}
        if(!reset && edges>=14 && read(7)!=1) {fail("missing reset release");return 0;}
        if(step>=220 && step<280 && read(10)!=external) {fail("unfrozen strap");return 0;}
        if(read(11)!=bypass) {fail("bypass routing");return 0;}
    }
    priorClock=expectedClock;checking=false;
    if(++step==700) {
        vpi_printf("PASS RESET_CELL_CONTRACT source=%d bypass=%d samples=%u\n",external,bypass,step);
        vpi_control(vpiFinish,0);
    } else schedule(apply,cbAfterDelay,1);
    return 0;
}
static PLI_INT32 apply(p_cb_data) {
    transitions=0;checking=true;
    const int rc=(step/3)%2,ext=(step/5)%2;
    expectedClock=external ? ext:rc;
    drive(0,rc);drive(1,ext);
    drive(2,!(step<60 || (step>=500 && step<520)));
    drive(3,!(step<40 || (step>=300 && step<320)));
    // Perturb only after qualification; restore before either new reset epoch.
    drive(4,(step>=220 && step<280) ? !external:external);drive(5,bypass);
    schedule(sample,cbReadOnlySynch);return 0;
}
static PLI_INT32 start(p_cb_data) {
    s_vpi_vlog_info info{};vpi_get_vlog_info(&info);
    for(int i=0;i<info.argc;++i) {
        if(std::string(info.argv[i])=="+external") external=1;
        if(std::string(info.argv[i])=="+bypass") bypass=1;
    }
    const char* names[]={"rcClock","externalAonClock","externalReset_n","supplyReset_n",
        "selectExternal","bypassPor","aonClock","aonReset_n","coldReset_n","warmReset_n",
        "selectedExternal","selectedBypass","strapsFrozen"};
    for(unsigned i=0;i<p.size();++i) {
        std::string name=std::string("ResetBootstrap.")+names[i];
        p[i]=vpi_handle_by_name(const_cast<char*>(name.c_str()),nullptr);
        if(!p[i]) {fail("missing port");return 0;}
    }
    s_cb_data cb{};cb.reason=cbValueChange;cb.cb_rtn=changed;cb.obj=p[6];
    vpi_register_cb(&cb);schedule(apply,cbAfterDelay,1);return 0;
}
static void initialize() {schedule(start,cbStartOfSimulation);}
extern "C" {void (*vlog_startup_routines[])()={initialize,nullptr};}
