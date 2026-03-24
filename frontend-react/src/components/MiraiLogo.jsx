import React from 'react';
import { motion } from 'framer-motion';

const MiraiLogo = ({ size = 48, className = '', animate = false }) => {
  const pathVariants = animate
    ? {
        hidden: { pathLength: 0, opacity: 0 },
        visible: (i) => ({
          pathLength: 1,
          opacity: 1,
          transition: { delay: i * 0.2, duration: 1.2, ease: 'easeInOut' },
        }),
      }
    : {};

  const Wrapper = animate ? motion.svg : 'svg';
  const Path = animate ? motion.path : 'path';
  const Circle = animate ? motion.circle : 'circle';

  return (
    <Wrapper
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      className={className}
      {...(animate ? { initial: 'hidden', animate: 'visible' } : {})}
    >
      {/* Outer ring */}
      <Circle
        cx="50"
        cy="50"
        r="46"
        stroke="url(#mirai-grad)"
        strokeWidth="2"
        fill="none"
        {...(animate ? { variants: pathVariants, custom: 0 } : {})}
      />
      {/* Inner hexagonal shape — stylized film reel */}
      <Path
        d="M50 12 L82 30 L82 70 L50 88 L18 70 L18 30 Z"
        stroke="url(#mirai-grad)"
        strokeWidth="1.5"
        fill="none"
        strokeLinejoin="round"
        {...(animate ? { variants: pathVariants, custom: 1 } : {})}
      />
      {/* M letter — stylized */}
      <Path
        d="M30 65 L30 38 L42 55 L50 42 L58 55 L70 38 L70 65"
        stroke="url(#mirai-grad)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        {...(animate ? { variants: pathVariants, custom: 2 } : {})}
      />
      {/* Center dot — projector light */}
      <Circle
        cx="50"
        cy="52"
        r="3"
        fill="#f59e0b"
        {...(animate
          ? {
              initial: { scale: 0, opacity: 0 },
              animate: {
                scale: [0, 1.4, 1],
                opacity: 1,
                transition: { delay: 1.5, duration: 0.6 },
              },
            }
          : {})}
      />
      <defs>
        <linearGradient id="mirai-grad" x1="0" y1="0" x2="100" y2="100">
          <stop offset="0%" stopColor="#f59e0b" />
          <stop offset="50%" stopColor="#d4a853" />
          <stop offset="100%" stopColor="#fbbf24" />
        </linearGradient>
      </defs>
    </Wrapper>
  );
};

export default MiraiLogo;
