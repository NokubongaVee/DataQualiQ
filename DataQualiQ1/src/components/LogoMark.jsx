import logo from '../assets/logo.png'

export default function LogoMark({ size = 38 }) {
  return (
    <img
      src={logo}
      alt="DataQualiQ logo"
      style={{ width: size, height: size, objectFit: 'contain' }}
    />
  );
}