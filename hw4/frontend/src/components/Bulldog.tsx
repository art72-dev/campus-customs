// A Yale-style bulldog drawn entirely with HTML elements + CSS (see .bulldog in index.css).
export default function Bulldog({
  size = 200,
  cap = false,
  tilt = 0,
  label = 'Campus Customs bulldog',
}: {
  size?: number
  cap?: boolean
  tilt?: number
  label?: string
}) {
  return (
    <div
      className="bulldog"
      role="img"
      aria-label={label}
      style={{ fontSize: size / 10, transform: `rotate(${tilt}deg)` }}
    >
      <div className="bd-ear bd-left" />
      <div className="bd-ear bd-right" />
      <div className="bd-head" />
      <div className="bd-blaze" />
      <div className="bd-wrinkle bd-w1" />
      <div className="bd-wrinkle bd-w2" />
      <div className="bd-eye bd-left" />
      <div className="bd-eye bd-right" />
      <div className="bd-muzzle" />
      <div className="bd-jowl bd-left" />
      <div className="bd-jowl bd-right" />
      <div className="bd-mouth" />
      <div className="bd-tooth bd-left" />
      <div className="bd-tooth bd-right" />
      <div className="bd-nose" />
      <div className="bd-collar" />
      <div className="bd-tag">Y</div>
      {cap && (
        <>
          <div className="bd-cap">Y</div>
          <div className="bd-brim" />
        </>
      )}
    </div>
  )
}
