#include "VFpu.h"
#include "verilated.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <array>
#include <cstdint>

int main(int argc,char **argv) {
  Verilated::commandArgs(argc,argv);
  if(argc!=2) return 2;
  VFpu d;
  auto edge=[&](){d.clock=0;d.eval();d.clock=1;d.eval();d.clock=0;d.eval();};
  d.clock=0;d.reset=1;d.io_cancel=0;d.io_req_valid=0;d.io_rsp_ready=0;d.eval();
  edge();d.reset=0;d.eval();
  std::ifstream file(argv[1]); std::string line; unsigned n=0;
  std::array<std::array<unsigned,5>,24> counts{};
  std::array<unsigned,24> maxcycles{};
  try {
    if(!file) throw std::runtime_error("missing vectors");
    while(std::getline(file,line)) {
      std::istringstream row(line); unsigned op,rm,flags; uint32_t a,b,c,result;
      if(!(row>>op>>rm>>std::hex>>a>>b>>c>>result>>flags)) throw std::runtime_error("malformed vector");
      if(op>=24 || rm>=5) throw std::runtime_error("invalid operation/rounding mode");
      const unsigned limit=op<=6 ? 38 : op==7 ? 58 : op==8 ? 56 :
                           (op==20 || op==21) ? 6 : op>=22 ? 8 : (op>=9 && op<=13) ? 4 : 3;
      if(!d.io_req_ready || d.io_busy || d.io_rsp_valid) throw std::runtime_error("not idle");
      d.io_req_bits_op=op;d.io_req_bits_rm=rm;
      d.io_req_bits_a=a;d.io_req_bits_b=b;d.io_req_bits_c=c;d.io_req_valid=1;
      edge();d.io_req_valid=0;
      d.io_req_bits_a=~a;d.io_req_bits_b=~b;d.io_req_bits_c=~c;
      d.io_req_bits_rm=(rm+1)%5;d.io_req_bits_op=(op+1)%24;
      unsigned cycles=0;
      while(!d.io_rsp_valid && cycles<limit) {
        if(d.io_req_ready || !d.io_busy) throw std::runtime_error("lost outstanding operation");
        edge();++cycles;
      }
      if(!d.io_rsp_valid) throw std::runtime_error("completion deadline");
      if(d.io_rsp_bits_result!=result || d.io_rsp_bits_flags!=flags) {
        std::cerr<<"vector "<<n<<" "<<line<<" actual "<<std::hex
                 <<d.io_rsp_bits_result<<" "<<(unsigned)d.io_rsp_bits_flags<<"\n";
        throw std::runtime_error("result/flags mismatch");
      }
      maxcycles[op]=std::max(maxcycles[op],cycles);counts[op][rm]++;
      for(unsigned i=0;i<n%3;i++) {
        edge();
        if(!d.io_rsp_valid || d.io_rsp_bits_result!=result || d.io_rsp_bits_flags!=flags ||
           !d.io_busy || d.io_req_ready) throw std::runtime_error("held response changed");
      }
      d.io_rsp_ready=1;edge();d.io_rsp_ready=0;++n;
    }
    if(!n) throw std::runtime_error("empty vectors");
    for(unsigned op=0;op<24;op++) {
      unsigned total=0;
      for(unsigned rm=0;rm<5;rm++) {
        if(!counts[op][rm]) throw std::runtime_error("missing operation/rounding mode pair");
        total+=counts[op][rm];
      }
      std::cout<<"OP "<<op<<" count="<<total<<" max_cycles="<<maxcycles[op]<<"\n";
    }
    std::cout<<"PASS "<<n<<" result/flags vectors and backpressure\n";
  } catch(const std::exception &e) { std::cerr<<"FAIL "<<e.what()<<"\n";return 1; }
}
