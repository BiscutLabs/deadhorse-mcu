package deadhorse.top

/** One fixed feature set. The only trial choices are frequency and USB stub.
  * Some-valued fields preserve existing connection/observation APIs; none can
  * be absent, and there is no feature-copy API or alternate production profile.
  */
final class SocI1Config(val mainMHz: Int=8,val realUsb: Boolean=true) {
  require(Set(8,9).contains(mainMHz))
  val uart="build/t20/i1/uart/uart_regs.json"
  val spi="build/t20/i1/spi_host/spi_host_regs.json"
  val i2c="build/t20/i1/i2c_host/i2c_host_regs.json"
  val mailbox="build/t20/i1/mailbox/mailbox_regs.json"
  val usb="build/t20/i1/usb/usb_regs.json"
  val oscCtrl="build/t20/i1/osc_ctrl/osc_ctrl_regs.json"
  val powerReset="build/t20/i1/power_reset/power_reset_regs.json"
  val sram="build/t20/i1/sram/sram_regs.json"
  val io: Option[SocIoConfig]=Some(SocIoConfig("build/t21/gpio/gpio_regs.json",
    "build/t21/timers/timers_regs.json","build/t21/aon_timer/aon_timer_regs.json",mainMHz))
  val pwm: Option[String]=Some("build/t22/pwm/pwm_regs.json")
  val dma: Option[String]=Some("build/t23/dma/dma_regs.json")
  val pinmux: Option[String]=Some("build/t24/pinmux/pinmux_regs.json")
  val liteCore=true
  val watchdog: Option[String]=Some("build/t26/watchdog/watchdog_regs.json")
  val bootControl: Option[String]=Some("build/t28/boot_control/boot_control_regs.json")
  val qspi: Option[String]=Some("build/t30/qspi/qspi_regs.json")
  val xip=true
}

object SocProduction {
  def config(mainMHz: Int=8,realUsb: Boolean=true): SocI1Config=new SocI1Config(mainMHz,realUsb)
}
