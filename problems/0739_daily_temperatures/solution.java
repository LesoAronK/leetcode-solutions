class Solution {
    public int[] dailyTemperatures(int[] temperatures) {
        int length = temperatures.length;
        Deque<Integer> stack = new ArrayDeque<>();
        int[] result = new int[length];
      
        for (int currentIndex = length - 1; currentIndex >= 0; currentIndex--) {

            while (!stack.isEmpty() && temperatures[stack.peek()] <= temperatures[currentIndex]) {
                stack.pop();
            }
          
            if (!stack.isEmpty()) {
                result[currentIndex] = stack.peek() - currentIndex;
            }
          
            stack.push(currentIndex);
        }
      
        return result;
    }
}